"""Prepare a Supabase reference-data trial. No network or main application writes."""
import csv
import hashlib
import io
import json
import math
import sqlite3
import zipfile
from pathlib import Path


NAMESPACE = 'reference_playground'
TITLES = {
    'minho-fatigue-v2': 'Minho dynamic sEMG and perceived fatigue',
    'don-carlo-gnocchi-upper-limb': 'Don Carlo Gnocchi post-stroke upper limb movement',
    'toronto-rehab-stroke-pose': 'Toronto Rehab Stroke Pose',
    'rehab-120': 'REHAB clinical kinematics',
    'bmfd': 'Biceps Muscular Failure sEMG',
}
DDL = '''
CREATE TABLE IF NOT EXISTS datasets (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, population TEXT NOT NULL,
 modalities TEXT NOT NULL, label_description TEXT NOT NULL,
 source_url TEXT NOT NULL, paper_url TEXT, license_status TEXT NOT NULL,
 data_origin TEXT NOT NULL CHECK(data_origin='external_public_reference'),
 training_eligible BOOLEAN NOT NULL DEFAULT FALSE CHECK(training_eligible=FALSE)
);
CREATE TABLE IF NOT EXISTS file_references (
 id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES datasets(id),
 filename TEXT NOT NULL, byte_count BIGINT NOT NULL CHECK(byte_count>0),
 sha256 TEXT NOT NULL, original_download_url TEXT NOT NULL,
 storage_status TEXT NOT NULL CHECK(storage_status='source_link_and_local_copy')
);
CREATE TABLE IF NOT EXISTS fatigue_trials (
 id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES datasets(id),
 subject_code TEXT NOT NULL, trial_number INTEGER NOT NULL CHECK(trial_number BETWEEN 1 AND 12),
 sample_count INTEGER NOT NULL CHECK(sample_count>1), first_time_s DOUBLE PRECISION NOT NULL,
 last_time_s DOUBLE PRECISION NOT NULL, nominal_sample_period_s DOUBLE PRECISION NOT NULL CHECK(nominal_sample_period_s>0),
 nonmonotonic_time_steps INTEGER NOT NULL CHECK(nonmonotonic_time_steps>=0),
 max_time_grid_error_s DOUBLE PRECISION NOT NULL CHECK(max_time_grid_error_s>=0),
 source_csv TEXT NOT NULL, csv_sha256 TEXT NOT NULL,
 label_meaning TEXT NOT NULL CHECK(label_meaning='self_perceived_0_2'),
 UNIQUE(dataset_id,subject_code,trial_number)
);
CREATE TABLE IF NOT EXISTS fatigue_segments (
 id TEXT PRIMARY KEY, trial_id TEXT NOT NULL REFERENCES fatigue_trials(id),
 segment_number INTEGER NOT NULL, first_sample INTEGER NOT NULL CHECK(first_sample>=0),
 end_sample_exclusive INTEGER NOT NULL CHECK(end_sample_exclusive>first_sample),
 first_recorded_time_s DOUBLE PRECISION NOT NULL, last_recorded_time_s DOUBLE PRECISION NOT NULL,
 label INTEGER NOT NULL CHECK(label BETWEEN 0 AND 2),
 UNIQUE(trial_id,segment_number)
);
'''


def sql_value(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Non-finite number')
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def make_insert(table, rows, prefix=''):
    if not rows:
        return ''
    columns = tuple(rows[0])
    values = ',\n'.join('(' + ','.join(sql_value(r[c]) for c in columns) + ')' for r in rows)
    return f'INSERT INTO {prefix}{table} ({",".join(columns)}) VALUES\n{values}\nON CONFLICT (id) DO NOTHING;\n'


def read_trials(archive):
    trials, segments, source_labels = [], [], {}
    with zipfile.ZipFile(archive) as outer:
        nested_name = 'self_perceived_fatigue_index/subject_1.zip'
        if outer.getinfo(nested_name).file_size > 10_000_000:
            raise ValueError('Unexpected nested archive size')
        with zipfile.ZipFile(io.BytesIO(outer.read(nested_name))) as nested:
            for number in range(1, 13):
                name = f'subject_1/Trial_{number}.csv'
                if nested.getinfo(name).file_size > 10_000_000:
                    raise ValueError('Unexpected CSV size')
                raw = nested.read(name)
                samples = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
                times = [float(r['time']) for r in samples]
                labels = [int(r['label']) for r in samples]
                if len(times) < 2 or any(not math.isfinite(t) for t in times):
                    raise ValueError('Invalid trial times')
                if any(v not in (0, 1, 2) for v in labels):
                    raise ValueError('Invalid fatigue level')
                period = 0.02
                nonmonotonic = sum(b <= a for a, b in zip(times, times[1:]))
                grid_error = max(abs(t - (times[0] + i * period)) for i, t in enumerate(times))
                trial_id = f'minho-v2-subject01-trial{number:02}'
                trials.append(dict(id=trial_id, dataset_id='minho-fatigue-v2', subject_code='minho_subject_01',
                                   trial_number=number, sample_count=len(labels), first_time_s=times[0],
                                   last_time_s=times[-1], nominal_sample_period_s=period,
                                   nonmonotonic_time_steps=nonmonotonic, max_time_grid_error_s=grid_error, source_csv=name,
                                   csv_sha256=hashlib.sha256(raw).hexdigest(), label_meaning='self_perceived_0_2'))
                start, segment_number = 0, 0
                for end in range(1, len(labels) + 1):
                    if end == len(labels) or labels[end] != labels[start]:
                        segments.append(dict(id=f'{trial_id}-segment{segment_number:02}', trial_id=trial_id,
                                             segment_number=segment_number, first_sample=start,
                                             end_sample_exclusive=end, first_recorded_time_s=times[start],
                                             last_recorded_time_s=times[end-1], label=labels[start]))
                        segment_number += 1
                        start = end
                source_labels[trial_id] = labels
    return trials, segments, source_labels


def build(sample_dir, catalog_path, output):
    if output.exists():
        raise FileExistsError(f'Preserve existing numbered output: {output}')
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    manifest = json.loads((sample_dir / 'download-manifest_v01.json').read_text(encoding='utf-8'))
    for item in manifest:
        raw = (sample_dir / item['name']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError(f'Source checksum mismatch: {item["name"]}')
    datasets = [dict(id=d['id'], title=TITLES[d['id']], population=d['population'],
                     modalities=json.dumps(d['modalities']), label_description=d.get('labels', d.get('tasks', '')),
                     source_url=d['data'], paper_url=d.get('paper'), license_status=d['license'],
                     data_origin='external_public_reference', training_eligible=False) for d in catalog['datasets']]
    files = [dict(id='file-' + item['name'], dataset_id='don-carlo-gnocchi-upper-limb' if item['name']=='ST03.mat' else 'minho-fatigue-v2',
                  filename=item['name'], byte_count=item['bytes'], sha256=item['sha256'],
                  original_download_url=item['download_url'], storage_status='source_link_and_local_copy') for item in manifest]
    trials, segments, original_labels = read_trials(sample_dir / 'self_perceived_fatigue_index.zip')
    tables = {'datasets':datasets, 'file_references':files, 'fatigue_trials':trials, 'fatigue_segments':segments}
    local_seed = '\n'.join(make_insert(k, v) for k, v in tables.items())
    with sqlite3.connect(':memory:') as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.executescript(DDL)
        connection.executescript(local_seed)
        connection.executescript(local_seed)
        for table, rows in tables.items():
            assert connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == len(rows)
        assert not connection.execute('PRAGMA foreign_key_check').fetchall()
        for trial in trials:
            restored = []
            rows = connection.execute('SELECT first_sample,end_sample_exclusive,label FROM fatigue_segments WHERE trial_id=? ORDER BY segment_number', (trial['id'],)).fetchall()
            for first, end, label in rows:
                assert first == len(restored)
                restored.extend([label] * (end - first))
            assert restored == original_labels[trial['id']], 'Source labels must reconstruct exactly'
        assert connection.execute('SELECT count(*) FROM datasets WHERE training_eligible<>FALSE').fetchone()[0] == 0
        try:
            connection.execute("UPDATE datasets SET training_eligible=TRUE WHERE id='minho-fatigue-v2'")
        except sqlite3.IntegrityError:
            connection.rollback()
        else:
            raise AssertionError('Reference-only constraint must reject training eligibility')

    output.mkdir(parents=True)
    qualified_ddl = DDL
    for name in tables:
        qualified_ddl = qualified_ddl.replace(f'EXISTS {name} ', f'EXISTS {NAMESPACE}.{name} ')
        qualified_ddl = qualified_ddl.replace(f'REFERENCES {name}(', f'REFERENCES {NAMESPACE}.{name}(')
    schema = '-- User-authorized AEII - 2026 project; only reference_playground is modified.\nBEGIN;\n'
    schema += f'CREATE SCHEMA IF NOT EXISTS {NAMESPACE};\n' + qualified_ddl
    for table in tables:
        schema += f'ALTER TABLE {NAMESPACE}.{table} ENABLE ROW LEVEL SECURITY;\n'
    schema += f'REVOKE ALL ON SCHEMA {NAMESPACE} FROM PUBLIC, anon, authenticated;\n'
    schema += f'REVOKE ALL ON ALL TABLES IN SCHEMA {NAMESPACE} FROM PUBLIC, anon, authenticated;\nCOMMIT;\n'
    seed = '-- Published reference data only; no current-project recordings.\nBEGIN;\n'
    seed += '\n'.join(make_insert(k, v, NAMESPACE + '.') for k, v in tables.items()) + '\nCOMMIT;\n'
    checks = f'''-- Owner/dashboard queries for the isolated trial project.
SELECT 'datasets' AS table_name, count(*) FROM {NAMESPACE}.datasets
UNION ALL SELECT 'files', count(*) FROM {NAMESPACE}.file_references
UNION ALL SELECT 'trials', count(*) FROM {NAMESPACE}.fatigue_trials
UNION ALL SELECT 'segments', count(*) FROM {NAMESPACE}.fatigue_segments;

-- Actual right/left biceps trials for the published sample participant.
SELECT t.subject_code,t.trial_number,s.label,
       s.first_recorded_time_s AS first_sample_time_s,
       s.last_recorded_time_s AS last_sample_time_s
FROM {NAMESPACE}.fatigue_trials t JOIN {NAMESPACE}.fatigue_segments s ON s.trial_id=t.id
WHERE t.trial_number IN (5,6) ORDER BY t.trial_number,s.segment_number;

-- Source/license lookup.
SELECT title,license_status,source_url FROM {NAMESPACE}.datasets ORDER BY title;

-- Keep clock anomalies visible; sample order has not been rewritten.
SELECT subject_code,trial_number,nonmonotonic_time_steps,max_time_grid_error_s
FROM {NAMESPACE}.fatigue_trials WHERE nonmonotonic_time_steps>0;
'''
    validation = dict(expected_project_name='AEII - 2026', expected_project_id='dpzmtmgfqudhfgykkcbf', schema=NAMESPACE,
                      cloud_status='prepared_no_network_writes', counts={k:len(v) for k,v in tables.items()},
                      source_samples=sum(t['sample_count'] for t in trials), exact_label_reconstruction=True,
                      timing_statistics_preserved=True,
                      nonmonotonic_trials=[t['trial_number'] for t in trials if t['nonmonotonic_time_steps']>0],
                      replay_is_idempotent=True, foreign_keys_pass=True,
                      training_eligibility_constraint_pass=True,
                      validation_boundary='Portable DDL/data checked with SQLite; PostgreSQL-specific schema, RLS and casts must be verified on the new Supabase project.')
    for filename, text in [('01_schema_v01.sql', schema), ('02_seed_v01.sql', seed), ('03_queries_v01.sql', checks)]:
        (output / filename).write_text(text,encoding='utf-8')
    (output / 'seed_data_v01.json').write_text(json.dumps(tables,indent=2),encoding='utf-8')
    (output / 'validation_v01.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
    print(json.dumps(validation,indent=2))


if __name__ == '__main__':
    project_root = Path(__file__).resolve().parents[2]
    build(project_root/'model/data/external_reference_v01',
          project_root/'CLAUDE/output/2026-11-09-clinical-data-sources_v01.json',
          Path(__file__).parent/'generated/v01')
