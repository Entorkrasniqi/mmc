"""Operations layer: objects, telemetry samples, audit log, outbox, and who may touch what.

Revision ID: 0001
Revises:

The tables follow ontology.md. The definition layer (parameters, packet types, command definitions) is NOT here:
it is generated from spec/minisat.yaml (ADR 0001), so tables refer to it by name or id without a foreign key.

Rules that are cheap to enforce in the database are enforced here as well as in the action runner, so that a bug in
one place cannot silently break them: the two-person rule for vital commands, "only a human approves or
acknowledges", lifecycle consistency, one open alarm per parameter, no overlapping contacts on one station,
and an audit log that nobody can change.
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    # ---------------------------------------------------------------------------------------- people
    """
    CREATE TABLE ops.operator (
        operator_id  text PRIMARY KEY,
        display_name text NOT NULL,
        kind         text NOT NULL CHECK (kind IN ('HUMAN', 'AGENT', 'SYSTEM')),
        role         text NOT NULL CHECK (role IN ('VIEWER', 'OPERATOR', 'SUPERVISOR', 'AGENT', 'SYSTEM')),
        created_at   timestamptz NOT NULL DEFAULT now(),
        UNIQUE (operator_id, kind),
        CHECK ((kind = 'HUMAN' AND role IN ('VIEWER', 'OPERATOR', 'SUPERVISOR'))
               OR (kind = 'AGENT' AND role = 'AGENT')
               OR (kind = 'SYSTEM' AND role = 'SYSTEM'))
    )""",
    # ---------------------------------------------------------------------------------------- things
    """
    CREATE TABLE ops.spacecraft (
        spacecraft_id   text PRIMARY KEY,
        name            text NOT NULL,
        health_status   text NOT NULL DEFAULT 'NOMINAL'
                        CHECK (health_status IN ('NOMINAL', 'WARNING', 'CRITICAL', 'SAFE_MODE')),
        last_contact_at timestamptz,
        -- newest value of every telemetry parameter, keyed by parameter name (the names come from the spec)
        latest_values   jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(latest_values) = 'object'),
        created_at      timestamptz NOT NULL DEFAULT now()
    )""",
    """
    CREATE TABLE ops.ground_station (
        station_id        text PRIMARY KEY,
        name              text NOT NULL,
        latitude_deg      double precision NOT NULL CHECK (latitude_deg BETWEEN -90 AND 90),
        longitude_deg     double precision NOT NULL CHECK (longitude_deg BETWEEN -180 AND 180),
        min_elevation_deg double precision NOT NULL DEFAULT 5 CHECK (min_elevation_deg BETWEEN 0 AND 90)
    )""",
    """
    CREATE TABLE ops.contact_window (
        contact_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        spacecraft_id     text NOT NULL REFERENCES ops.spacecraft,
        station_id        text NOT NULL REFERENCES ops.ground_station,
        start_at          timestamptz NOT NULL,
        end_at            timestamptz NOT NULL,
        max_elevation_deg double precision CHECK (max_elevation_deg BETWEEN 0 AND 90),
        status            text NOT NULL DEFAULT 'PLANNED'
                          CHECK (status IN ('PLANNED', 'ACTIVE', 'COMPLETED', 'MISSED')),
        packets_received  integer NOT NULL DEFAULT 0 CHECK (packets_received >= 0),
        packets_lost      integer NOT NULL DEFAULT 0 CHECK (packets_lost >= 0),
        created_by        text NOT NULL REFERENCES ops.operator,
        created_at        timestamptz NOT NULL DEFAULT now(),
        CHECK (end_at > start_at),
        -- one station cannot serve two contacts at the same time (a missed pass frees the slot)
        EXCLUDE USING gist (station_id WITH =, tstzrange(start_at, end_at) WITH &&) WHERE (status <> 'MISSED')
    )""",
    # ---------------------------------------------------------------------------------------- problems
    """
    CREATE TABLE ops.anomaly (
        anomaly_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        spacecraft_id   text NOT NULL REFERENCES ops.spacecraft,
        title           text NOT NULL CHECK (length(btrim(title)) > 0),
        severity        text NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH')),
        status          text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'INVESTIGATING', 'RESOLVED')),
        detected_at     timestamptz NOT NULL DEFAULT now(),
        resolved_at     timestamptz,
        root_cause      text,
        resolution_note text,
        opened_by       text NOT NULL REFERENCES ops.operator,
        -- anomalies are resolved, never deleted; resolving needs a root cause
        CHECK ((status = 'RESOLVED') = (resolved_at IS NOT NULL)),
        CHECK (status <> 'RESOLVED' OR length(btrim(coalesce(root_cause, ''))) > 0),
        CHECK (resolved_at IS NULL OR resolved_at >= detected_at)
    )""",
    """
    CREATE TABLE ops.alarm (
        alarm_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        spacecraft_id   text NOT NULL REFERENCES ops.spacecraft,
        parameter_name  text NOT NULL,
        severity        text NOT NULL CHECK (severity IN ('WARNING', 'CRITICAL')),
        trigger_value   double precision NOT NULL,
        limit_violated  text NOT NULL,
        state           text NOT NULL DEFAULT 'ACTIVE' CHECK (state IN ('ACTIVE', 'ACKNOWLEDGED', 'CLEARED')),
        raised_at       timestamptz NOT NULL DEFAULT now(),
        cleared_at      timestamptz,
        acknowledged_by text,
        -- only a person can take responsibility for an alarm: the pair must match a HUMAN operator
        acknowledged_by_kind text GENERATED ALWAYS AS (CASE WHEN acknowledged_by IS NULL THEN NULL ELSE 'HUMAN' END) STORED,
        acknowledged_at timestamptz,
        acknowledge_note text,
        anomaly_id      uuid REFERENCES ops.anomaly,
        FOREIGN KEY (acknowledged_by, acknowledged_by_kind) REFERENCES ops.operator (operator_id, kind),
        CHECK ((acknowledged_by IS NULL) = (acknowledged_at IS NULL)),
        CHECK (state <> 'ACTIVE' OR acknowledged_by IS NULL),
        CHECK (state <> 'ACKNOWLEDGED' OR acknowledged_by IS NOT NULL),
        CHECK ((state = 'CLEARED') = (cleared_at IS NOT NULL)),
        CHECK (cleared_at IS NULL OR cleared_at >= raised_at)
    )""",
    # one open alarm per parameter and spacecraft: an alarm is an episode, and it may escalate from WARNING to CRITICAL
    "CREATE UNIQUE INDEX alarm_one_open_per_parameter ON ops.alarm (spacecraft_id, parameter_name) WHERE state <> 'CLEARED'",
    # ---------------------------------------------------------------------------------------- commands
    """
    CREATE TABLE ops.command_execution (
        execution_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        spacecraft_id        text NOT NULL REFERENCES ops.spacecraft,
        command_id           integer NOT NULL CHECK (command_id BETWEEN 1 AND 65535),
        command_name         text NOT NULL,
        -- the definition's significance when it was proposed; a later spec change must not weaken an old record
        vital                boolean NOT NULL,
        arguments            jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(arguments) = 'object'),
        reason               text NOT NULL CHECK (length(btrim(reason)) > 0),
        status               text NOT NULL DEFAULT 'PROPOSED'
                             CHECK (status IN ('PROPOSED', 'APPROVED', 'RELEASED', 'SENT', 'ACCEPTED',
                                               'REJECTED_ONBOARD', 'VERIFIED', 'FAILED', 'CANCELLED')),
        rejection_reason     text,
        proposed_by          text NOT NULL REFERENCES ops.operator,
        approved_by          text,
        -- only a person approves (an agent proposes): the pair must match a HUMAN operator
        approved_by_kind     text GENERATED ALWAYS AS (CASE WHEN approved_by IS NULL THEN NULL ELSE 'HUMAN' END) STORED,
        responds_to_alarm_id uuid REFERENCES ops.alarm,
        contact_id           uuid REFERENCES ops.contact_window,
        raw_bytes_hex        text CHECK (raw_bytes_hex IS NULL OR raw_bytes_hex ~ '^([0-9a-f]{2})+$'),
        proposed_at          timestamptz NOT NULL DEFAULT now(),
        expires_at           timestamptz NOT NULL,
        approved_at          timestamptz,
        released_at          timestamptz,
        sent_at              timestamptz,
        verified_at          timestamptz,
        FOREIGN KEY (approved_by, approved_by_kind) REFERENCES ops.operator (operator_id, kind),
        CHECK (expires_at > proposed_at),
        -- two-person rule: a vital command is never approved by whoever proposed it
        CHECK (approved_by IS NULL OR NOT vital OR approved_by <> proposed_by),
        CHECK ((approved_by IS NULL) = (approved_at IS NULL)),
        -- nothing goes beyond PROPOSED without an approver
        CHECK (status IN ('PROPOSED', 'CANCELLED') OR approved_by IS NOT NULL),
        CHECK (status <> 'REJECTED_ONBOARD' OR length(btrim(coalesce(rejection_reason, ''))) > 0)
    )""",
    "CREATE INDEX command_execution_by_spacecraft ON ops.command_execution (spacecraft_id, proposed_at DESC)",
    "CREATE INDEX command_execution_open ON ops.command_execution (spacecraft_id) WHERE status NOT IN "
    "('VERIFIED', 'REJECTED_ONBOARD', 'FAILED', 'CANCELLED')",
    """
    CREATE TABLE ops.anomaly_command_execution (
        anomaly_id   uuid NOT NULL REFERENCES ops.anomaly,
        execution_id uuid NOT NULL REFERENCES ops.command_execution,
        PRIMARY KEY (anomaly_id, execution_id)
    )""",
    # ---------------------------------------------------------------------------------------- observations
    """
    CREATE TABLE ops.spacecraft_event (
        event_id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        spacecraft_id            text NOT NULL REFERENCES ops.spacecraft,
        event_type               text NOT NULL CHECK (event_type IN ('MODE_CHANGE', 'FDIR', 'REBOOT', 'ECLIPSE_ENTRY',
                                                                      'ECLIPSE_EXIT', 'COMMAND_ACCEPTED',
                                                                      'COMMAND_REJECTED')),
        occurred_at              timestamptz NOT NULL,
        details                  jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object'),
        caused_by_execution_id   uuid REFERENCES ops.command_execution,
        recorded_at              timestamptz NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX spacecraft_event_by_time ON ops.spacecraft_event (spacecraft_id, occurred_at DESC)",
    # one value of one parameter at one spacecraft time; a time series, not an object (ontology.md, TelemetrySample)
    """
    CREATE TABLE ops.telemetry_samples (
        spacecraft_id    text NOT NULL REFERENCES ops.spacecraft,
        parameter_name   text NOT NULL,
        sc_time_ms       bigint NOT NULL CHECK (sc_time_ms >= 0),
        received_at      timestamptz NOT NULL DEFAULT now(),
        value            double precision NOT NULL,
        packet_seq_count integer CHECK (packet_seq_count BETWEEN 0 AND 16383),
        PRIMARY KEY (spacecraft_id, parameter_name, sc_time_ms)
    )""",
    # ---------------------------------------------------------------------------------------- bookkeeping
    """
    CREATE TABLE ops.audit_log (
        audit_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        occurred_at     timestamptz NOT NULL DEFAULT now(),
        -- no foreign key: a refused attempt by an unknown caller must still be recorded
        operator_id     text,
        operator_kind   text CHECK (operator_kind IN ('HUMAN', 'AGENT', 'SYSTEM')),
        action          text NOT NULL,
        outcome         text NOT NULL CHECK (outcome IN ('OK', 'DENIED', 'INVALID', 'ERROR')),
        parameters      jsonb NOT NULL DEFAULT '{}'::jsonb,
        before          jsonb,
        after           jsonb,
        correlation_id  uuid,
        idempotency_key text
    )""",
    # a retried request with the same key must not be applied twice
    "CREATE UNIQUE INDEX audit_log_idempotency ON ops.audit_log (action, idempotency_key) "
    "WHERE idempotency_key IS NOT NULL AND outcome = 'OK'",
    "CREATE INDEX audit_log_by_correlation ON ops.audit_log (correlation_id) WHERE correlation_id IS NOT NULL",
    """
    CREATE FUNCTION ops.audit_log_is_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
                              MESSAGE = 'ops.audit_log is append-only: ' || TG_OP || ' refused';
    END $$""",
    # a trigger, not just missing grants: it also stops the owner and superusers (unless they drop the trigger)
    "CREATE TRIGGER audit_log_no_change BEFORE UPDATE OR DELETE ON ops.audit_log "
    "FOR EACH ROW EXECUTE FUNCTION ops.audit_log_is_append_only()",
    "CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON ops.audit_log "
    "FOR EACH STATEMENT EXECUTE FUNCTION ops.audit_log_is_append_only()",
    # side effects wait here until after the action's transaction has committed (protocols/action-runner-and-audit.md)
    """
    CREATE TABLE ops.outbox (
        outbox_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        topic          text NOT NULL,
        payload        jsonb NOT NULL,
        correlation_id uuid,
        created_at     timestamptz NOT NULL DEFAULT now(),
        available_at   timestamptz NOT NULL DEFAULT now(),
        processed_at   timestamptz,
        attempts       integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        last_error     text
    )""",
    "CREATE INDEX outbox_pending ON ops.outbox (available_at) WHERE processed_at IS NULL",
]

GRANTS = [
    "GRANT USAGE ON SCHEMA ops TO app_runner, app_reader, ingest",
    # reader: read everything
    "GRANT SELECT ON ALL TABLES IN SCHEMA ops TO app_reader",
    # runner: the only role that writes the operations tables. It never deletes anything and never changes the
    # schema. Operators, stations and spacecraft are reference data created by administrators, not by actions.
    "GRANT SELECT ON ALL TABLES IN SCHEMA ops TO app_runner",
    "GRANT UPDATE (health_status) ON ops.spacecraft TO app_runner",
    "GRANT INSERT, UPDATE ON ops.contact_window, ops.anomaly, ops.alarm, ops.command_execution, ops.outbox "
    "TO app_runner",
    "GRANT INSERT ON ops.anomaly_command_execution, ops.spacecraft_event, ops.audit_log TO app_runner",
    # ingest: append samples and refresh the newest values of a spacecraft; nothing else
    "GRANT SELECT ON ops.spacecraft, ops.telemetry_samples TO ingest",
    "GRANT INSERT ON ops.telemetry_samples TO ingest",
    "GRANT UPDATE (latest_values, last_contact_at) ON ops.spacecraft TO ingest",
]


def upgrade() -> None:
    missing = op.get_bind().exec_driver_sql(
        "SELECT r FROM unnest(ARRAY['app_runner', 'app_reader', 'ingest']) AS r "
        "WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = r)").fetchall()
    if missing:
        raise RuntimeError("database roles missing: " + ", ".join(r[0] for r in missing) +
                           " (create them first with db/roles.sql)")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")        # for the "no overlapping contacts" constraint
    op.execute("CREATE SCHEMA ops")
    for statement in TABLES + GRANTS:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP SCHEMA ops CASCADE")
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
