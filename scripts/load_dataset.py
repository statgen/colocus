"""
Load a packaged dataset from the specific directory into the app

This checks:
1. Metadata is present (crawl YML in folder, get or create for every file)
  - Copies over file objects to internal storage
2. Coloc signals get loaded. One signal per YML file.
3.
"""
import argparse
import gzip
import heapq
import logging
import os
import pathlib
import sys
import time
import typing as ty
import polars as pl
import numpy as np
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from subprocess import PIPE, Popen, check_output

import django
import yaml
from django.conf import settings

# Must configure standalone django usage before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
sys.path.append(str(Path(__file__).parent.parent.resolve()))
django.setup()

# Setup logger
logger = logging.getLogger(__name__)

from colocus.core.models import (  # noqa E402
    ColocResult,
    DataSubmission,
    Exon,
    FineMappedSignal,
    FineMappingProgram,
    Gene,
    LDStats,
    LeadVariant,
    MarginalAnalysis,
    Phenotype,
    Publication,
    Study,
    Trait,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Load a packaged coloc dataset into the database. Assumes validation "
                                                 "was performed elsewhere, eg for uuid integrity")
    parser.add_argument('input', help='The top level folder of the packaged dataset with a predefined '
                                      'structure.', nargs="+")
    return parser.parse_args()


def _save_file_to_file(field, local_filename: pathlib.Path):
    # NOTE: Django will automatically try to prevent overwriting files with same name, which might not be intended
    # behavior given how controlled our scheme is
    base_name = local_filename.name  # Most fields control save name, but provide one for clarity
    with open(local_filename, 'rb') as f:
        field.save(base_name, f)


def load_submission(package_root: pathlib.Path) -> DataSubmission:
    meta_path = package_root / "metadata.yml"
    if not meta_path.exists():
        raise Exception('No analysis package found')

    with open(meta_path, 'r') as f:
        metadata = yaml.safe_load(f)

    try:
        # We don't use get_or_create because additional NOT NULL fields may be required
        ds = DataSubmission.objects.get(uuid=metadata['uuid'])
    except DataSubmission.DoesNotExist:
        ds = init_model(DataSubmission, metadata)

    metadata["ingest_date"] = datetime.utcnow()
    for k, v in metadata.items():
        setattr(ds, k, v)

    ds.save()
    return ds


def touch_if_exists(path):
    if os.path.exists(path):
        os.utime(path, None)


def tabix(fpath):
    tbi = fpath + ".tbi"

    check_output(f"tabix -f -c '#' -s 4 -b 5 -e 5 {fpath}", shell=True)

    while not (os.path.exists(tbi) and os.path.getsize(tbi) > 0):
        time.sleep(0.1)

    touch_if_exists(tbi)


def merge_ld_files(out_path, *paths):
    bgzip_proc = Popen(f"bgzip -c > {out_path}", stdin=PIPE, shell=True, text=True)

    def line_iter(file):
        for line in file:
            ls = line.split('\t')
            # TODO: this seems strange to me that LD is sorted on columns 4,5 (1-index) first, then 1,2.
            # Need to revisit pipelines generating the LD data and see why that is
            sort_key = (ls[3], int(ls[4]), ls[0], int(ls[1]))
            yield sort_key, line

    with ExitStack() as stack:
        handles = []

        for path in paths:
            handles.append(stack.enter_context(gzip.open(path, 'rt')))

        for _, line in heapq.merge(*[line_iter(f) for f in handles], key=lambda x: x[0]):
            bgzip_proc.stdin.write(line)
            bgzip_proc.stdin.flush()

    bgzip_proc.stdin.close()
    stdout, stderr = bgzip_proc.communicate()


def load_ld(data_sub, ld_dir: pathlib.Path) -> LDStats:
    meta_path = ld_dir / "metadata.yml"
    if not meta_path.exists():
        raise Exception('No analysis package found')

    with open(meta_path, 'r') as f:
        metadata = yaml.safe_load(f)

    # Check UUID format
    correct_uuid = f"{metadata['panel']}_{metadata['genome_build']}_{metadata['population']}"
    if metadata['uuid'] != correct_uuid:
        raise Exception(f"UUID {metadata['uuid']} does not match expected format {correct_uuid}")

    # Check if there are any other LD files that are the same panel / build / population.
    # If so, we need to merge them into a single file.
    matching = LDStats.objects.filter(
        panel=metadata['panel'],
        genome_build=metadata['genome_build'],
        population=metadata['population']
    )

    found_ld = matching.exists()

    if found_ld and len(matching) > 1:
        raise Exception(f"Multiple LD files found for panel {metadata['panel']}, build {metadata['genome_build']}, "
                        f"population {metadata['population']}. There should only be a single entry in the database.")

    db_ld_path = None
    if found_ld:
        # The first result is the currently existing LD file in the database
        ld = matching[0]
        db_ld_path = ld.ld_data.name
        db_ld_full_path = os.path.join(settings.MEDIA_ROOT, db_ld_path)

        # The LD data we are currently processing
        cur_ld_path = ld_dir / 'ld.gz'

        # We are going to store the merged LD file in the same location as the existing LD file in the database
        final_ld_path = db_ld_full_path

        # We need a temporary file to store the merged LD file, can't overwrite the existing file at the same time we
        # read from it
        temp_ld_path = db_ld_full_path + ".tmp"

        # Perform the merge, including bgzip and tabixing the final LD file
        logger.info(f"Previously seen LD found for "
                    f"{metadata['panel']} {metadata['genome_build']} {metadata['population']}")
        logger.info(f"Merging {db_ld_full_path} & {cur_ld_path} → {final_ld_path} using temporary file {temp_ld_path}")
        merge_ld_files(
            temp_ld_path,
            db_ld_full_path,
            cur_ld_path
        )

        # Move the temporary file to the final location and overwrite existing file
        os.replace(temp_ld_path, final_ld_path)

        # Tabix the final file in-place
        tabix(final_ld_path)

        logger.info(f"Final LD file saved to {final_ld_path} for "
                    f"{metadata['panel']} {metadata['genome_build']} {metadata['population']}")

    try:
        # Don't use get_or_create because additional non-null fields exist
        ld = LDStats.objects.get(uuid=metadata['uuid'])
        for k, v in metadata.items():
            setattr(ld, k, v)
    except LDStats.DoesNotExist:
        ld = LDStats(**metadata)

    ld.data_submission = data_sub

    if not found_ld:
        # If we didn't find existing LD, then we need to go through the normal process of saving
        # the LD file, and storing the LD metadata/path in the database
        logger.info(f"Saving LD file for {metadata['panel']} {metadata['genome_build']} {metadata['population']}")
        _save_file_to_file(ld.ld_data, ld_dir / 'ld.gz')
        _save_file_to_file(ld.ld_data_tbi, ld_dir / 'ld.gz.tbi')
    else:
        ld.ld_data = db_ld_path
        ld.ld_data_tbi = db_ld_path + ".tbi"

    ld.save()

    return ld


def init_model(model, attrs: dict):
    """
    Load a model with the specified attribute values, ignoring any dict fields not present in the model

    Allows YML files to specify additional info useful to the build process, without breaking the DB loader script
    """
    return model(**{k: v for k, v in attrs.items() if k in [f.name for f in model._meta.get_fields()]})


def get_by_id_or_create(model, id_field, id_value, attrs: dict):
    try:
        return model.objects.get(**{id_field: id_value})
    except model.DoesNotExist:
        m = init_model(model, attrs)
        m.save()
        return m


def load_one_signal(
    data_submission: DataSubmission,
    analysis: MarginalAnalysis,
    signal_dir: pathlib.Path
) -> ty.Optional[FineMappedSignal]:
    """
    Load a single fine mapped signal + conditional analysis results

    A metadata.yml file for this will look something like:

    ```
    uuid: VV2ycPVcUnrg1Pa9Vcyuox
    lead_variant:
      alt: A
      chrom: '7'
      pos: 157020640
      ref: C
      vid: "7_157020640_C_A"
    effect_cond: -4.205
    effect_marg: -0.497
    neg_log_p: 4.844
    se_cond: 0.9691
    finemap_program:
      name: SuSiE
      version: 0.7.1
    ```
    """

    meta_path = signal_dir / 'metadata.parquet'
    if not meta_path.exists():
        raise Exception(f'Signal must specify metadata as {meta_path}')

    metadata = pl.read_parquet(meta_path).to_dicts().pop()

    if "lead_variant" not in metadata:
        raise Exception('Signal metadata must specify `lead_variant` block')

    # Get the lead variant for this fine-mapped signal
    # We want a brand new `LeadVariant` each time; it is a utility class to keep track of the variant & its statistics
    # but those statistics (neg_log_p, effect, se, etc.) change depending on the associated trait and analysis
    lv_dict = metadata.pop("lead_variant")
    lv_dict["vid"] = lv_dict["chrom"] + "_" + str(lv_dict["pos"]) + "_" + lv_dict["ref"] + "_" + lv_dict["alt"]
    lead_variant = LeadVariant.objects.create(**lv_dict)

    # Get fine-mapping program used
    program, _ = FineMappingProgram.objects.get_or_create(**metadata.pop("finemap_program"))

    metadata["lead_variant"] = lead_variant
    metadata["analysis"] = analysis
    metadata["program"] = program

    # Create a signal. This should never have existed previously. If it did, the `unique=True` check on the model should
    # kick it back when we try to save it.
    signal = FineMappedSignal(**metadata)

    _save_file_to_file(signal.cond_analysis, signal_dir / 'results.harmonized.gz')
    _save_file_to_file(signal.cond_analysis_tbi, signal_dir / 'results.harmonized.gz.tbi')

    signal.save()
    return signal


def load_one_marginal(data_submission: DataSubmission, analysis_dir: pathlib.Path) -> MarginalAnalysis:
    """
    Load a single marginal analysis + all signals contained in subdirectories.

    The `analysis_dir` is the top level folder for a single trait, which contains a metadata.yml file and a set of
    subfolders, one per signal.

    The `metadata.yml` file will look something like:

    ```
    uuid: "eqtl_adipoexpress_ENSG0101401401"
    analysis_type: "eqtl"
    description: 'AdipoExpress Adipose eQTL analysis for ENSG0104141'
    publication:
      authors: "Mahajan et al. (Nature Genetics 2022)"
      pmid: 35551307
    trait:
      uuid: "ENSG01040141041"
      gene:
        ens_id: "ENSG101041041401"
        symbol: "TCF7L2"
      tissue: "adipose"
      biomarker_type: "gene-expression"
    study:
      name: "AdipoExpress"
      description: "AdipoExpress eQTL Meta-Analysis"
    external_link: "https://www.adipoexpress.org/"
    genome_build: "GRCh37"
    ld_panel: "ukbb_grch37_all_muscislet"
    ```
    """

    meta_path = analysis_dir / 'metadata.parquet'
    if not meta_path.exists():
        raise Exception(f'Marginal trait must specify metadata as {meta_path}')

    metadata = pl.read_parquet(meta_path).to_dicts().pop()

    try:
        marginal = MarginalAnalysis.objects.get(uuid=metadata['uuid'])
    except MarginalAnalysis.DoesNotExist:
        marginal = MarginalAnalysis()

    for k, v in metadata.items():
        if k == 'ld_panel':
            marginal.ld = LDStats.objects.get(uuid=v)
        elif k == 'publication':
            pub, created = Publication.objects.get_or_create(**v)
            marginal.publication = pub
        elif k == 'study':
            study = get_by_id_or_create(Study, 'uuid', v['uuid'], v)
            marginal.study = study
        elif k == 'trait':
            gene = v.pop('gene', None)
            exon = v.pop('exon', None)
            pheno = v.pop('phenotype', None)

            # trait, created = Trait.objects.get_or_create(**v)
            trait = get_by_id_or_create(Trait, 'uuid', v['uuid'], v)

            if gene:
                # gene, created = Gene.objects.get_or_create(**gene)
                gene = get_by_id_or_create(Gene, 'ens_id', gene['ens_id'], gene)
                trait.gene = gene

            if exon:
                exon["gene"] = gene
                # exon, created = Exon.objects.get_or_create(**exon)
                exon = get_by_id_or_create(Exon, 'ens_id', exon['ens_id'], exon)
                trait.exon = exon

            if pheno:
                # pheno, created = Phenotype.objects.get_or_create(**pheno)
                if "uuid" not in pheno:
                    pheno["uuid"] = v["uuid"]
                pheno = get_by_id_or_create(Phenotype, 'uuid', pheno['uuid'], pheno)
                trait.phenotype = pheno

            trait.save()
            marginal.trait = trait
        else:
            setattr(marginal, k, v)

    marginal.data_submission = data_submission

    _save_file_to_file(marginal.summary_stats, analysis_dir / 'summ_stats.harmonized.gz')

    manhattan_path = analysis_dir / 'manhattan.json'
    qq_path = analysis_dir / 'qq.json'

    # Only GWAS traits (not eQTLs!) have a manhattan plot file. Don't require it for QTLs.
    if manhattan_path.exists():
        _save_file_to_file(marginal.manhattan_bins, manhattan_path)

    if qq_path.exists():
        _save_file_to_file(marginal.qq_bins, qq_path)

    _save_file_to_file(marginal.summary_stats_tbi, analysis_dir / 'summ_stats.harmonized.gz.tbi')

    marginal.save()

    # Load all independent signals identified for this trait
    signals_path = analysis_dir / "signals"
    for signal in signals_path.iterdir():
        if not signal.is_dir():
            continue
        load_one_signal(data_submission, marginal, signal)

    return marginal

def ndarray_to_list(matrix):
    matrix = np.where(np.isnan(matrix), None, matrix)
    return [x.tolist() for x in matrix]

def load_colocalizations(data_submission: DataSubmission, coloc_file: pathlib.Path) -> ColocResult:
    """Load colocalization results"""

    colocs = pl.read_parquet(coloc_file)

    if len(colocs) == 0:
        raise Exception(f"No colocalization results found in file {coloc_file}")

    for meta_dict in colocs.iter_rows(named=True):
        try:
            coloc = ColocResult.objects.get(uuid=meta_dict['uuid'])
        except ColocResult.DoesNotExist:
            coloc = ColocResult()

        # # Convert numpy arrays to lists
        # for o, e in meta_dict["cross_signal"].items():
        #     meta_dict["cross_signal"][o] = ndarray_to_list(e)

        for k, v in meta_dict.items():
            if k not in {"data_submission", "signal1", "signal2"}:
                setattr(coloc, k, v)

        coloc.data_submission = data_submission

        # An external validation step should have already verified that signal1 and signal2 exist
        coloc.signal1 = FineMappedSignal.objects.get(uuid=meta_dict['signal1'])
        coloc.signal2 = FineMappedSignal.objects.get(uuid=meta_dict['signal2'])

        coloc.save()

def main(package_root: str):
    path = pathlib.Path(package_root).resolve()
    if not path.exists():
        raise Exception(f'Package directory does not exist: {path}')

    # Load parent analysis
    data_sub = load_submission(path)

    # Load possible LD panels
    ld_dir = path / "ld"
    for panel in ld_dir.iterdir():
        if not panel.is_dir():
            continue
        load_ld(data_sub, panel)

    # Load each marginal trait + all signals contained in child folders
    marg_dir = path / "marginal"
    if not marg_dir.exists():
        raise Exception("No marginal trait information provided")

    for analysis_dir in marg_dir.glob("*/*"):
        if not analysis_dir.is_dir():
            continue
        logger.info(f"Loading marginal analyses from {analysis_dir}")
        load_one_marginal(data_sub, analysis_dir)

    coloc_file = path / "coloc" / "coloc.parquet"
    if not coloc_file.exists():
        raise Exception(f'Must provide colocalization results as {coloc_file}')

    logger.info("Loading colocalizations")
    load_colocalizations(data_sub, coloc_file)


if __name__ == '__main__':
    args = parse_args()
    for source_dir in args.input:
        logger.info(f"Loading dataset from: {source_dir}")
        main(source_dir)
