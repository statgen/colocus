"""
Utilities for locating key study files. Generates upload filenames for FileFields.

This exists because Django requires that file upload fields calculate default path using functions, not lambdas.
"""

import os


def get_marginal_summstats(instance, filename):
    return os.path.join("marginal", instance.uuid, "marginal.gz")


def get_marginal_summstats_tbi(instance, filename):
    return os.path.join("marginal", instance.uuid, "marginal.gz.tbi")


def get_manhattan(instance, filename):
    return os.path.join("marginal", instance.uuid, "manhattan.json")


def get_qq(instance, filename):
    return os.path.join("marginal", instance.uuid, "qq.json")


def get_signals_cond(instance, filename):
    return os.path.join("signals", instance.uuid, "cond_analysis.gz")


def get_signals_cond_tbi(instance, filename):
    return os.path.join("signals", instance.uuid, "cond_analysis.gz.tbi")


def get_ld_filename(instance, filename):
    ld_dir = f"{instance.panel}_{instance.genome_build}_{instance.population}"
    return os.path.join("ld", ld_dir, "ld.gz")


def get_ld_filename_tbi(instance, filename):
    ld_dir = f"{instance.panel}_{instance.genome_build}_{instance.population}"
    return os.path.join("ld", ld_dir, "ld.gz.tbi")
