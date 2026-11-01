"""What an approver needs to see, who cancelled what, and more kinds of spacecraft events.

Revision ID: 0002
Revises: 0001

* command_execution keeps the preflight result, the spacecraft state it was based on, the effect telemetry should show
  (for verification), the telemetry at the moment of sending (the baseline for that check), the approver's note, who
  cancelled it and why, and the reason for releasing without a contact window.
* spacecraft_event gets PACKET_LOSS, LINK_LOST and LINK_RESTORED, and a link to the anomaly it belongs to.

Downgrading fails if events of the new kinds exist: they are records, and a migration must not delete records.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

OLD_EVENT_TYPES = ("MODE_CHANGE", "FDIR", "REBOOT", "ECLIPSE_ENTRY", "ECLIPSE_EXIT", "COMMAND_ACCEPTED",
                   "COMMAND_REJECTED")
NEW_EVENT_TYPES = OLD_EVENT_TYPES + ("PACKET_LOSS", "LINK_LOST", "LINK_RESTORED")


def _in(values):
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ops.command_execution
            ADD COLUMN preflight       jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(preflight) = 'object'),
            ADD COLUMN state_snapshot  jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(state_snapshot) = 'object'),
            ADD COLUMN expected_effect jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(expected_effect) = 'array'),
            ADD COLUMN send_baseline   jsonb CHECK (send_baseline IS NULL OR jsonb_typeof(send_baseline) = 'object'),
            ADD COLUMN approval_note   text,
            ADD COLUMN cancelled_by    text REFERENCES ops.operator,
            ADD COLUMN cancel_reason   text,
            ADD COLUMN override_reason text,
            -- who cancelled, and why, is always recorded
            ADD CONSTRAINT command_execution_cancel_recorded
                CHECK (status <> 'CANCELLED'
                       OR (cancelled_by IS NOT NULL AND length(btrim(coalesce(cancel_reason, ''))) > 0)),
            -- verification compares telemetry with what it looked like when the command was sent
            ADD CONSTRAINT command_execution_sent_has_baseline
                CHECK (status NOT IN ('SENT', 'ACCEPTED', 'REJECTED_ONBOARD', 'VERIFIED', 'FAILED')
                       OR send_baseline IS NOT NULL)""")
    op.execute("ALTER TABLE ops.spacecraft_event DROP CONSTRAINT spacecraft_event_event_type_check")
    op.execute(f"ALTER TABLE ops.spacecraft_event ADD CONSTRAINT spacecraft_event_event_type_check "
               f"CHECK (event_type IN ({_in(NEW_EVENT_TYPES)}))")
    op.execute("ALTER TABLE ops.spacecraft_event ADD COLUMN anomaly_id uuid REFERENCES ops.anomaly")
    op.execute("CREATE INDEX spacecraft_event_by_anomaly ON ops.spacecraft_event (anomaly_id) WHERE anomaly_id IS NOT NULL")
    op.execute("GRANT UPDATE (anomaly_id) ON ops.spacecraft_event TO app_runner")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (anomaly_id) ON ops.spacecraft_event FROM app_runner")
    op.execute("DROP INDEX ops.spacecraft_event_by_anomaly")
    op.execute("ALTER TABLE ops.spacecraft_event DROP COLUMN anomaly_id")
    op.execute("ALTER TABLE ops.spacecraft_event DROP CONSTRAINT spacecraft_event_event_type_check")
    op.execute(f"ALTER TABLE ops.spacecraft_event ADD CONSTRAINT spacecraft_event_event_type_check "
               f"CHECK (event_type IN ({_in(OLD_EVENT_TYPES)}))")
    op.execute("""
        ALTER TABLE ops.command_execution
            DROP CONSTRAINT command_execution_sent_has_baseline,
            DROP CONSTRAINT command_execution_cancel_recorded,
            DROP COLUMN override_reason, DROP COLUMN cancel_reason, DROP COLUMN cancelled_by,
            DROP COLUMN approval_note, DROP COLUMN send_baseline, DROP COLUMN expected_effect,
            DROP COLUMN state_snapshot, DROP COLUMN preflight""")
