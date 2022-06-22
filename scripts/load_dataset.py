"""
Load a packaged dataset from the specific directory into the app

This checks:
1. Metadata is present (crawl YML in folder, get_or_create for every file)
  - Copies over file objects to internal storage
2. Coloc signals get loaded. One signal per YML file.
3.
"""
from datetime import datetime
import os
from pathlib import Path
import sys

import django
import pathlib
import yaml

from colocus.core.models import AnalysisGroup, ColocPair, LDPairs, MarginalSignal, MarginalTrait

# Must configure standalone django usage before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
sys.path.append(str(Path(__file__).parent.parent.resolve()))
django.setup()


def load_analysis(package_root: pathlib.Path) -> AnalysisGroup:
    meta_path = package_root / "metadata.yml"
    if not meta_path.exists():
        raise Exception('No analysis package found')

    with open(meta_path, 'r') as f:
        metadata = yaml.load(f)

    analysis = AnalysisGroup.objects.get_or_create(uuid=metadata['uuid'])

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
        metadata = yaml.load(f)

    ld = LDPairs.objects.get_or_create(uuid=metadata['uuid'])
    for k, v in metadata.items():
        setattr(ld, k, v)

    ld.analysis = analysis
    ld.save()
    return ld


def load_one_signal(analysis: AnalysisGroup, marginal: MarginalTrait, signal_dir: pathlib.Path) -> MarginalSignal:
    meta_path = signal_dir / 'metadata.yml'
    if not meta_path.exists():
        raise Exception(f'Signal must specify metadata as {meta_path}')

    with open(meta_path, 'r') as f:
        metadata = yaml.load(f)

    signal = ColocSignal.objects.get_or_create(uuid=metadata['uuid'])
    for k, v in metadata.items():
        setattr(signal, k, v)

    signal.analysis = analysis
    signal.trait = marginal

    signal.cond_analysis = signal_dir / 'cond_analysis.gz'
    signal.cond_analysis_tbi = signal_dir / 'cond_analysis.gz.tbi'

    signal.save()
    return signal


def load_one_marginal(analysis: AnalysisGroup, trait_dir: pathlib.Path) -> MarginalTrait:
    meta_path = trait_dir / 'metadata.yml'
    if not meta_path.exists():
        raise Exception(f'Marginal trait must specify metadata as {meta_path}')

    with open(meta_path, 'r') as f:
        metadata = yaml.load(f)

    marginal = MarginalTrait.objects.get_or_create(uuid=metadata['uuid'])
    for k, v in metadata.items():
        setattr(marginal, k, v)

    marginal.analysis = analysis

    # FIXME: Can this handle a local path? How does upload_to work in this case? need to work out create / save logic
    marginal.summary_stats = trait_dir / 'summ_stats.gz'
    marginal.summary_stats_tbi = trait_dir / 'summ_stats.gz.tbi'
    marginal.manhattan_bins = trait_dir / 'manhattan.json'
    marginal.qq_bins = trait_dir / 'qq.json'

    marginal.save()

    # Load all independent signals identified for this trait
    signals_path = trait_dir / "signals"
    for signal in signals_path.iterdir():
        if not signal.is_dir():
            continue

        load_one_signal(analysis, marginal, signal)

    return marginal


def load_one_colocalization(analysis: AnalysisGroup, signal_dir: pathlib.Path) -> ColocPair:
    """Load colocalization results (one signal pair)"""
    meta_path = signal_dir / 'metadata.yml'
    if not meta_path.exists():
        raise Exception(f'Marginal trait must specify metadata as {meta_path}')

    with open(meta_path, 'r') as f:
        metadata = yaml.load(f)

    coloc = ColocPair.objects.get_or_create(uuid=metadata['uuid'])
    for k, v in metadata.items():
        if k not in {"signal1, signal2"}:
            setattr(coloc, k, v)

    # An external validation step should have already verified that signal1 and signal2 exist
    coloc.signal1 = MarginalSignal.objects.get(uuid=metadata['signal1'])
    coloc.signal2 = MarginalSignal.objects.get(uuid=metadata['signal2'])

    coloc.save()
    return coloc


def main(package_root: str):
    path = pathlib.Path(package_root).resolve()
    if not path.exists():
        raise Exception(f'Package directory does not exist: {path}')

    # Load parent analysis
    analysis = load_analysis(path)

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
        # This directory contains a list of subfolders, one colocalized signal pair (and results) per folder
        if not coloc.is_dir():
            continue

        load_one_colocalization(analysis, coloc)
