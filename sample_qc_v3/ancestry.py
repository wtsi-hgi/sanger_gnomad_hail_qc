import os
import hail as hl
import pandas as pd
import pyspark
import json
import sys
import re
from pathlib import Path
import logging
from typing import Any, Counter, List, Optional, Tuple, Union
from bokeh.plotting import output_file, save, show
from gnomad_ancestry import pc_project, run_pca_with_relateds, assign_population_pcs

logging.basicConfig(format="%(levelname)s (%(name)s %(lineno)s): %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


POP_NAMES = {
    "afr": "African/African-American",
    "ami": "Amish",
    "amr": "Latino",
    "asj": "Ashkenazi Jewish",
    "eas": "East Asian",
    "eur": "European",
    "fin": "Finnish",
    "mde": "Middle Eastern",
    "nfe": "Non-Finnish European",
    "oth": "Other",
    "sas": "South Asian",
    "uniform": "Uniform",
    "sas_non_consang": "South Asian (F < 0.05)",
    "consanguineous": "South Asian (F > 0.05)",
    "exac": "ExAC",
    "bgr": "Bulgarian (Eastern European)",
    "est": "Estonian",
    "gbr": "British",
    "nwe": "North-Western European",
    "seu": "Southern European",
    "swe": "Swedish",
    "kor": "Korean",
    "sgp": "Singaporean",
    "jpn": "Japanese",
    "oea": "Other East Asian",
    "oeu": "Other European",
    "onf": "Other Non-Finnish European",
    "unk": "Unknown",
}

POP_COLORS = {
    "afr": "#941494",
    "ami": "#FFC0CB",
    "amr": "#ED1E24",
    "asj": "#FF7F50",
    "eas": "#108C44",
    "eur": "#6AA5CD",
    "fin": "#002F6C",
    "mde": "#33CC33",
    "nfe": "#6AA5CD",
    "oth": "#ABB9B9",
    "sas": "#FF9912",
    "uniform": "pink",
    "consanguineous": "pink",
    "sas_non_consang": "orange",
    "exac": "gray",
    "bgr": "#66C2A5",
    "est": "black",
    "gbr": "#C60C30",
    "nwe": "#C60C30",
    "seu": "#3CA021",
    "swe": "purple",
    "kor": "#4891D9",
    "sgp": "darkred",
    "jpn": "#BC002D",
    "oea": "#108C44",
    "oeu": "#6AA5CD",
    "onf": "#6AA5CD",
    "unk": "#ABB9B9",
    "": "#ABB9B9",
}


def get_reference_genome(
    locus: Union[hl.expr.LocusExpression, hl.expr.IntervalExpression],
    add_sequence: bool = False,
) -> hl.ReferenceGenome:
    """
    Returns the reference genome associated with the input Locus expression
    :param locus: Input locus
    :param add_sequence: If set, the fasta sequence is added to the reference genome
    :return: Reference genome
    """
    if isinstance(locus, hl.expr.LocusExpression):
        ref = locus.dtype.reference_genome
    else:
        assert isinstance(locus, hl.expr.IntervalExpression)
        ref = locus.dtype.point_type.reference_genome
    if add_sequence:
        ref = add_reference_sequence(ref)
    return ref


def filter_to_autosomes(
    t: Union[hl.MatrixTable, hl.Table]
) -> Union[hl.MatrixTable, hl.Table]:
    """
    Filters the Table or MatrixTable to autosomes only.
    This assumes that the input contains a field named `locus` of type Locus
    :param t: Input MT/HT
    :return:  MT/HT autosomes
    """
    reference = get_reference_genome(t.locus)
    autosomes = hl.parse_locus_interval(
        f"{reference.contigs[0]}-{reference.contigs[21]}", reference_genome=reference
    )
    return hl.filter_intervals(t, [autosomes])


project_root = Path(__file__).parent.parent
print(project_root)

s3credentials = os.path.join(
    project_root, "hail_configuration_files/s3_credentials.json")
print(s3credentials)

storage = os.path.join(project_root, "hail_configuration_files/storage.json")

thresholds = os.path.join(
    project_root, "hail_configuration_files/thresholds.json")

with open(f"{s3credentials}", 'r') as f:
    credentials = json.load(f)

with open(f"{storage}", 'r') as f:
    storage = json.load(f)

with open(f"{thresholds}", 'r') as f:
    thresholds = json.load(f)

if __name__ == "__main__":
    # need to create spark cluster first before intiialising hail
    sc = pyspark.SparkContext()
    # Define the hail persistent storage directory
    tmp_dir = "hdfs://spark-master:9820/"
    temp_dir = os.path.join(os.environ["HAIL_HOME"], "tmp")
    hl.init(sc=sc, tmp_dir=tmp_dir, default_reference="GRCh38")
    # s3 credentials required for user to access the datasets in farm flexible compute s3 environment
    # you may use your own here from your .s3fg file in your home directory
    hadoop_config = sc._jsc.hadoopConfiguration()

    hadoop_config.set("fs.s3a.access.key", credentials["mer"]["access_key"])
    hadoop_config.set("fs.s3a.secret.key", credentials["mer"]["secret_key"])

    # mt = hl.read_matrix_table(
    #    f"{temp_dir}/ddd-elgh-ukbb/chr1_chr20_XY_sex_annotations.mt")

    # ld pruning
    # pruned_ht = hl.ld_prune(mt.GT, r2=0.1)
    # pruned_mt = mt.filter_rows(hl.is_defined(pruned_ht[mt.row_key]))
    # pruned_mt.write(
    #    f"{tmp_dir}/ddd-elgh-ukbb/chr1_chr20_XY_ldpruned.mt", overwrite=True)
    pruned_mt = hl.read_matrix_table(
        f"{temp_dir}/ddd-elgh-ukbb/relatedness_ancestry/ddd-elgh-ukbb/chr1_chr20_XY_ldpruned.mt")

    related_samples_to_drop = hl.read_table(
        f"{temp_dir}/ddd-elgh-ukbb/relatedness_ancestry/ddd-elgh-ukbb/chr1_chr20_XY_related_samples_to_remove.ht")

    logger.info("run_pca_with_relateds")
    pca_results = run_pca_with_relateds(
        pruned_mt, related_samples_to_drop)
    pca_results.write(f"{tmp_dir}/ddd-elgh-ukbb/pca_results.ht")
    pca_results = pca_results.annotate(known_pop="unk")
    #pca_scores.write(f"{tmp_dir}/ddd-elgh-ukbb/pca_scores.ht", overwrite=True)
    #pca_loadings.write(f"{tmp_dir}/ddd-elgh-ukbb/pca_loadings.ht", overwrite=True)
    #pca_scores = hl.read_table(f"{temp_dir}/ddd-elgh-ukbb/pca_scores.ht")
    #pca_loadings = hl.read_table(f"{temp_dir}/ddd-elgh-ukbb/pca_loadings.ht")
    logger.info("assign population pcs")
    population_assignment_table = assign_population_pcs(
        pca_results, known_col="known_pop")

    population_assignment_table.write(
        f"{tmp_dir}/ddd-elgh-ukbb/pop_assignments.ht")