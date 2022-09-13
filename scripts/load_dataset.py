"""
Load a packaged dataset from the specific directory into the app

This checks:
1. Metadata is present (crawl YML in folder, get or create for every file)
  - Copies over file objects to internal storage
2. Coloc signals get loaded. One signal per YML file.
3.
"""
import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
import typing as ty

import django
import pathlib
import yaml

# Must configure standalone django usage before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
sys.path.append(str(Path(__file__).parent.parent.resolve()))
django.setup()

from colocus.core.models import AnalysisGroup, ColocResult, LDPairs, MarginalSignal, MarginalTrait


def parse_args():
    parser = argparse.ArgumentParser(description="Load a packaged coloc dataset into the database. Assumes validation was performed elsewhere, eg for uuid integrity")
    parser.add_argument('input', help='The top level folder of the packaged dataset with a predefined structure.')
    return parser.parse_args()

def _save_file_to_file(field, local_filename: pathlib.Path):
    # NOTE: Django will automatically try to prevent overwriting files with same name, which might not be intended behavior given how controlled our scheme is
    base_name = local_filename.name  # Most fields control save name, but provide one for clarity
    with open(local_filename, 'rb') as f:
        field.save(base_name, f)


def load_analysis(package_root: pathlib.Path) -> AnalysisGroup:
    meta_path = package_root / "metadata.yml"
    if not meta_path.exists():
        raise Exception('No analysis package found')

    with open(meta_path, 'r') as f:
        metadata = yaml.safe_load(f)

    try:
        # We don't use get_or_create because additional NOT NULL fields may be required
        analysis = AnalysisGroup.objects.get(uuid=metadata['uuid'])
    except AnalysisGroup.DoesNotExist:
        analysis = AnalysisGroup(**metadata)

    metadata["ingest_date"] = datetime.utcnow()
    for k, v in metadata.items():
        setattr(analysis, k, v)

    analysis.save()
    return analysis


def load_ld(analysis, ld_dir: pathlib.Path) -> LDPairs:
    meta_path = ld_dir / "metadata.yml"
    if not meta_path.exists():
        raise Exception('No analysis package found')

    with open(meta_path, 'r') as f:
        metadata = yaml.safe_load(f)

    try:
        # Don't use get_or_create because additional non-null fields exist
        ld = LDPairs.objects.get(analysis__uuid=analysis.uuid, uuid=metadata['uuid'])
        for k, v in metadata.items():
            setattr(ld, k, v)
    except LDPairs.DoesNotExist:
        ld = LDPairs(**metadata)

    ld.analysis = analysis

    _save_file_to_file(ld.ld_data, ld_dir / 'ld.gz')
    _save_file_to_file(ld.ld_data_tbi, ld_dir / 'ld.gz.tbi')

    ld.save()
    return ld


def load_one_signal(analysis: AnalysisGroup, trait: MarginalTrait, signal_dir: pathlib.Path) -> ty.Optional[MarginalSignal]:
    meta_path = signal_dir / 'metadata.yml'
    if not meta_path.exists():
        raise Exception(f'Signal must specify metadata as {meta_path}')

    with open(meta_path, 'r') as f:
        metadata = yaml.safe_load(f)

    if 'error' in metadata:
        # FIXME: some Ryan metadata files contain errors instead of data. If that happens, skip ingesting this signal.
        #  Eventually those bad yml files will cease to exist and this can be removed.
        return

    # FIXME: Temp pop keys not in official schema
    for k in ['original_file', 'lead_variant_assoc_gene', 'original_lead_variant_marker']:
        if k in metadata:
            metadata.pop(k)

    try:
        # Don't use get_or_create because additional non-null fields exist
        signal = MarginalSignal.objects.get(analysis__uuid=analysis.uuid, uuid=metadata['uuid'])
    except MarginalSignal.DoesNotExist:
        signal = MarginalSignal(**metadata)
    except Exception as e:
        print(meta_path)
        print(metadata)
        raise e

    for k, v in metadata.items():
        setattr(signal, k, v)

    signal.analysis = analysis
    signal.trait = trait

    _save_file_to_file(signal.cond_analysis, signal_dir / 'cond_analysis.harmonized.gz')
    _save_file_to_file(signal.cond_analysis_tbi, signal_dir / 'cond_analysis.harmonized.gz.tbi')

    signal.save()
    return signal


def load_one_marginal(analysis: AnalysisGroup, trait_dir: pathlib.Path) -> MarginalTrait:
    meta_path = trait_dir / 'metadata.yml'
    if not meta_path.exists():
        raise Exception(f'Marginal trait must specify metadata as {meta_path}')

    with open(meta_path, 'r') as f:
        metadata = yaml.safe_load(f)

    try:
        marginal = MarginalTrait.objects.get(analysis__uuid=analysis.uuid, uuid=metadata['uuid'])
    except MarginalTrait.DoesNotExist:
        marginal = MarginalTrait()

    for k, v in metadata.items():
        if k == 'ld_panel':
            marginal.ld = LDPairs.objects.get(uuid=v)
        else:
            setattr(marginal, k, v)

    marginal.analysis = analysis

    # FIXME: Can this handle a local path? How does upload_to work in this case? need to work out create / save logic
    _save_file_to_file(marginal.summary_stats, trait_dir / 'summ_stats.harmonized.gz')

    manhattan_path = trait_dir / 'manhattan.json'
    qq_path = trait_dir / 'qq.json'

    # Only GWAS traits (not eQTLs!) have a manhattan plot file. Don't require it for QTLs.
    if manhattan_path.exists():
        _save_file_to_file(marginal.manhattan_bins, manhattan_path)

    if qq_path.exists():
        _save_file_to_file(marginal.qq_bins, qq_path)

    _save_file_to_file(marginal.summary_stats_tbi, trait_dir / 'summ_stats.harmonized.gz.tbi')
    # FIXME: Generate these files and add back to pipeline
    # _save_file_to_file(marginal.manhattan_bins, trait_dir / 'manhattan.json')
    # _save_file_to_file(marginal.qq_bins, trait_dir / 'qq.json')

    marginal.save()

    # Load all independent signals identified for this trait
    signals_path = trait_dir / "signals"
    for signal in signals_path.iterdir():
        if not signal.is_dir():
            continue
        load_one_signal(analysis, marginal, signal)

    return marginal


def load_one_colocalization(analysis: AnalysisGroup, signal_dir: pathlib.Path) -> ColocResult:
    """Load colocalization results (one signal pair)"""
    meta_path = signal_dir / 'metadata.yml'
    if not meta_path.exists():
        raise Exception(f'Marginal trait must specify metadata as {meta_path}')

    with open(meta_path, 'r') as f:
        metadata = yaml.safe_load(f)

    try:
        coloc = ColocResult.objects.get(analysis__uuid=analysis.uuid, uuid=metadata['uuid'])
    except ColocResult.DoesNotExist:
        coloc = ColocResult()

    for k, v in metadata.items():
        if k not in {"signal1", "signal2"}:
            setattr(coloc, k, v)

    coloc.analysis = analysis
    # An external validation step should have already verified that signal1 and signal2 exist
    coloc.signal1 = MarginalSignal.objects.get(analysis__uuid=analysis.uuid, uuid=metadata['signal1'])
    coloc.signal2 = MarginalSignal.objects.get(analysis__uuid=analysis.uuid, uuid=metadata['signal2'])

    coloc.save()
    return coloc


def main(package_root: str):
    path = pathlib.Path(package_root).resolve()
    if not path.exists():
        raise Exception(f'Package directory does not exist: {path}')

    # Load parent analysis
    analysis = load_analysis(path)

    # Load possible LD panels
    ld_dir = path / "ld"
    for panel in ld_dir.iterdir():
        if not panel.is_dir():
            continue
        load_ld(analysis, panel)

    # Load each marginal trait + all signals contained in child folders
    traits_dir = path / "marginal"
    if not traits_dir.exists():
        raise Exception("No marginal trait information provided")

    for trait in traits_dir.iterdir():
        if not trait.is_dir():
            continue
        load_one_marginal(analysis, trait)

    coloc_dir = path / "coloc"
    if not coloc_dir.exists():
        raise Exception(f'Must provide colocalized signal information under {coloc_dir}')

    for coloc in coloc_dir.iterdir():
        # This directory contains a list of subfolders, one colocalized signal pair
        #   (and possibly supporting results) per folder
        if not coloc.is_dir():
            continue
        load_one_colocalization(analysis, coloc)


if __name__ == '__main__':
    args = parse_args()
    source_dir = args.input
    main(source_dir)
