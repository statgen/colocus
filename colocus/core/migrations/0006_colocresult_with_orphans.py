from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_finemappedsignal_cs_alpha_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
CREATE MATERIALIZED VIEW core_colocresult_with_orphans AS
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
  FROM core_finemappedsignal fs
  JOIN core_marginalanalysis ma ON ma.id = fs.analysis_id
  LEFT JOIN core_colocresult cr1 ON fs.id = cr1.signal1_id
  LEFT JOIN core_colocresult cr2 ON fs.id = cr2.signal2_id
  WHERE cr1.id IS NULL AND cr2.id IS NULL
) combined_results;

-- Create indexes since we're now using a materialized view
CREATE UNIQUE INDEX idx_colocresult_orphans_id ON core_colocresult_with_orphans (id);
CREATE INDEX idx_colocresult_orphans_signal1 ON core_colocresult_with_orphans (signal1_id);
CREATE INDEX idx_colocresult_orphans_signal2 ON core_colocresult_with_orphans (signal2_id);
            """,
            reverse_sql="DROP MATERIALIZED VIEW IF EXISTS core_colocresult_with_orphans;"
        ),
    ]
