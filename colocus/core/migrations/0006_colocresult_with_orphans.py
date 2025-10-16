from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_finemappedsignal_cs_alpha_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
CREATE VIEW core_colocresult_with_orphans AS
SELECT
  ROW_NUMBER() OVER (ORDER BY uuid) as id,
  uuid,
  cross_signal,
  coloc_h3,
  coloc_h4,
  r2,
  n_coloc_between_traits,
  data_submission_id,
  signal1_id,
  signal2_id
FROM (
  -- Real colocalization results
  SELECT
    uuid,
    cross_signal,
    coloc_h3,
    coloc_h4,
    r2,
    n_coloc_between_traits,
    data_submission_id,
    signal1_id,
    signal2_id
  FROM core_colocresult

  UNION ALL

  -- Fine-mapped signals that do not exist in the colocalization results
  SELECT
    fs.uuid as uuid,
    NULL::jsonb as cross_signal,
    0.0::float8 as coloc_h3,
    0.0::float8 as coloc_h4,
    0.0::float8 as r2,
    0::integer as n_coloc_between_traits,
    ma.data_submission_id as data_submission_id,
    fs.id as signal1_id,
    NULL::integer as signal2_id
  FROM core_finemappedsignal fs, core_marginalanalysis ma
  WHERE fs.id NOT IN (
    SELECT signal1_id FROM core_colocresult WHERE signal1_id IS NOT NULL
    UNION
    SELECT signal2_id FROM core_colocresult WHERE signal2_id IS NOT NULL
  ) AND ma.id = fs.analysis_id
) combined_results;
            """,
            reverse_sql="DROP VIEW IF EXISTS core_colocresult_with_orphans;"
        ),
    ]
