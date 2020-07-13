import os
import hail as hl
import pyspark
import json
import sys
import re
import pandas as pd 
from pathlib import Path

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

    #####################################################################
    ###################### INPUT DATA  ##############################
    #####################################################################
    sample_qc_table=f"{temp_dir}/ddd-elgh-ukbb/tables/chr1_sampleQC_unfiltered.tsv.bgz"
    df=pd.read_csv(sample_qc_table, compression='gzip',delimiter="\t")
    samples_per_cohort = df.groupby("cohort")["s"].count()
    fig = px.bar(samples_per_cohort, x='s',
            text='s',
             labels={'s':'Samples'}, height=1000).update_yaxes(categoryorder="category descending")
    fig.update_layout(title=f"Number of samples per cohort in dataset. (93674 samples in total)")