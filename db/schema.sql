-- Schema local PostgreSQL — ĐẦY ĐỦ theo docs/11-sql-khoi-tao-db-may-local-python-postgres.md
-- (sao lại đúng nguyên bản mục 4 của tài liệu, không rút gọn nữa).
--
-- Thay thế bản rút gọn trước đó (local_scan_records dùng chassis_rear TEXT) —
-- giờ dùng đúng profile_id INTEGER theo spec, xem db/seed_full_schema.py để
-- biết profile_id ứng với chassis_rear nào (sinh từ data/mapping_store.py).

BEGIN;

CREATE SCHEMA IF NOT EXISTS local_qr;
SET search_path TO local_qr, public;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'local_scan_status'
  ) THEN
    CREATE TYPE local_qr.local_scan_status AS ENUM ('OK', 'NG');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'server_scan_status'
  ) THEN
    CREATE TYPE local_qr.server_scan_status AS ENUM ('OK', 'NG', 'SKIPPED', 'PENDING', 'UNKNOWN');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'final_scan_status'
  ) THEN
    CREATE TYPE local_qr.final_scan_status AS ENUM ('OK', 'NG', 'PENDING', 'PENDING_SERVER');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'local_sync_status'
  ) THEN
    CREATE TYPE local_qr.local_sync_status AS ENUM (
      'LOCAL_ONLY',
      'PENDING',
      'SYNCING',
      'SYNCED',
      'FAILED_RETRYABLE',
      'FAILED_BLOCKED'
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'duplicate_local_scope'
  ) THEN
    CREATE TYPE local_qr.duplicate_local_scope AS ENUM ('DAY', 'PROFILE', 'MACHINE', 'MACHINE_DAY');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'sync_batch_trigger_type'
  ) THEN
    CREATE TYPE local_qr.sync_batch_trigger_type AS ENUM (
      'STARTUP',
      'SHUTDOWN',
      'NETWORK_RESTORED',
      'MANUAL'
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'sync_batch_status'
  ) THEN
    CREATE TYPE local_qr.sync_batch_status AS ENUM (
      'PENDING',
      'SENDING',
      'DONE',
      'PARTIAL_FAILED',
      'FAILED'
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'machine_command_type'
  ) THEN
    CREATE TYPE local_qr.machine_command_type AS ENUM (
      'SYNC_PROFILE',
      'SYNC_SCAN_DATA',
      'RELOAD_CONFIG',
      'SHOW_MESSAGE'
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'command_local_status'
  ) THEN
    CREATE TYPE local_qr.command_local_status AS ENUM (
      'PENDING',
      'RUNNING',
      'ACKED',
      'FAILED',
      'SKIPPED'
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'command_ack_status'
  ) THEN
    CREATE TYPE local_qr.command_ack_status AS ENUM ('ACK', 'FAILED');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'local_notification_severity'
  ) THEN
    CREATE TYPE local_qr.local_notification_severity AS ENUM ('INFO', 'WARNING', 'ERROR', 'CRITICAL');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'local_notification_status'
  ) THEN
    CREATE TYPE local_qr.local_notification_status AS ENUM ('NEW', 'READ', 'DISMISSED');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'local_notification_source'
  ) THEN
    CREATE TYPE local_qr.local_notification_source AS ENUM ('LOCAL', 'SERVER_COMMAND', 'SERVER_RESPONSE');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'api_request_method'
  ) THEN
    CREATE TYPE local_qr.api_request_method AS ENUM ('GET', 'POST', 'PATCH', 'PUT', 'DELETE');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'local_qr' AND t.typname = 'app_event_level'
  ) THEN
    CREATE TYPE local_qr.app_event_level AS ENUM ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL');
  END IF;
END $$;

-- Tính năng Rework NG (docs/13-huong-dan-rework-cho-may-local.md) — 3 giá trị
-- enum mới. PHẢI là câu lệnh top-level, KHÔNG được bọc trong DO $$ ... END $$
-- (Postgres cấm ALTER TYPE ... ADD VALUE chạy bên trong DO/hàm PL/pgSQL).
-- IF NOT EXISTS đã tự idempotent, chạy lại nhiều lần vô hại.
ALTER TYPE local_qr.local_scan_status ADD VALUE IF NOT EXISTS 'REWORK';
ALTER TYPE local_qr.final_scan_status ADD VALUE IF NOT EXISTS 'REWORK';
ALTER TYPE local_qr.final_scan_status ADD VALUE IF NOT EXISTS 'NG_REWORK';

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS id_counters (
  counter_name TEXT NOT NULL,
  counter_date DATE NOT NULL DEFAULT CURRENT_DATE,
  current_value BIGINT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (counter_name, counter_date)
);

CREATE TABLE IF NOT EXISTS local_app_settings (
  id SMALLINT PRIMARY KEY DEFAULT 1,
  server_host TEXT NOT NULL DEFAULT '127.0.0.1',
  api_port INTEGER NOT NULL DEFAULT 3979 CHECK (api_port BETWEEN 1 AND 65535),
  machine_code TEXT NOT NULL DEFAULT 'LOCAL01',
  machine_serial TEXT,
  machine_uid TEXT,
  machine_license_key TEXT,
  registration_request_id TEXT,
  registration_status TEXT NOT NULL DEFAULT 'NOT_REQUESTED' CHECK (registration_status IN ('NOT_REQUESTED', 'PENDING', 'APPROVED', 'REJECTED', 'DUPLICATE')),
  license_activated_at TIMESTAMPTZ,
  active_profile_id INTEGER,
  app_version TEXT,
  local_db_version TEXT NOT NULL DEFAULT '20260713.001',
  duplicate_scope duplicate_local_scope NOT NULL DEFAULT 'DAY',
  server_online BOOLEAN NOT NULL DEFAULT false,
  local_runtime_status TEXT NOT NULL DEFAULT 'BOOTING' CHECK (
    local_runtime_status IN (
      'BOOTING',
      'SERVER_OFFLINE',
      'NOT_REGISTERED',
      'REGISTERING',
      'WAITING_LICENSE',
      'WAITING_APPROVAL',
      'REJECTED',
      'READY',
      'SCANNING',
      'SYNCING',
      'BLOCKED',
      'ERROR'
    )
  ),
  local_status_message TEXT,
  local_status_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_health_at TIMESTAMPTZ,
  last_config_sync_at TIMESTAMPTZ,
  last_heartbeat_at TIMESTAMPTZ,
  last_server_error_code TEXT,
  last_server_error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT local_app_settings_single_row CHECK (id = 1)
);

CREATE TABLE IF NOT EXISTS server_settings_cache (
  id SMALLINT PRIMARY KEY DEFAULT 1,
  factory_code_default TEXT NOT NULL DEFAULT 'DZLV',
  full_code_length_default INTEGER NOT NULL DEFAULT 35,
  full_vendor_position_default INTEGER NOT NULL DEFAULT 18,
  led_scan_length_default INTEGER NOT NULL DEFAULT 22,
  led_vendor_position_default INTEGER NOT NULL DEFAULT 16,
  duplicate_days INTEGER NOT NULL DEFAULT 30,
  heartbeat_timeout_seconds INTEGER NOT NULL DEFAULT 60,
  raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  synced_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT server_settings_cache_single_row CHECK (id = 1)
);

-- Migration: bảng đã tồn tại từ trước (default cũ 'DYS3') thì đổi default cho
-- đúng docs/11(2).md — không đụng dữ liệu đã có, seed_full_schema.py tự ghi
-- đè giá trị thật.
ALTER TABLE server_settings_cache ALTER COLUMN factory_code_default SET DEFAULT 'DZLV';

CREATE TABLE IF NOT EXISTS machine_cache (
  machine_code TEXT PRIMARY KEY,
  server_machine_id INTEGER,
  machine_name TEXT NOT NULL,
  serial TEXT,
  uid TEXT,
  line_name TEXT,
  station_name TEXT,
  ip_address TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true,
  raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  synced_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Vendor không còn nằm cố định trong profile (1 chassis có thể có nhiều
-- vendor LED hợp lệ) — local lấy vendor từ ký tự thứ 18 của full code rồi
-- tra bảng này.
CREATE TABLE IF NOT EXISTS vendor_cache (
  vendor_id INTEGER,
  vendor_name TEXT NOT NULL,
  vendor_char TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'PENDING', 'DISABLED')),
  raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  synced_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS profile_cache (
  profile_id INTEGER PRIMARY KEY,
  version INTEGER NOT NULL DEFAULT 1,
  chassis_code_id INTEGER,
  chassis_code_full TEXT NOT NULL,
  chassis_code_input TEXT,
  factory_code TEXT NOT NULL,
  full_code_length INTEGER NOT NULL DEFAULT 35,
  full_vendor_position INTEGER NOT NULL DEFAULT 18,
  led_scan_length INTEGER NOT NULL DEFAULT 22,
  led_vendor_position INTEGER NOT NULL DEFAULT 16,
  is_active BOOLEAN NOT NULL DEFAULT true,
  raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  synced_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Migration: bảng profile_cache đã tồn tại từ trước (còn 3 cột vendor_*) thì
-- xoá đi, dữ liệu vendor giờ nằm ở vendor_cache.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'local_qr' AND table_name = 'profile_cache' AND column_name = 'vendor_char'
  ) THEN
    ALTER TABLE profile_cache DROP COLUMN vendor_id;
    ALTER TABLE profile_cache DROP COLUMN vendor_name;
    -- CASCADE vì v_active_profiles còn tham chiếu cột này — view sẽ được
    -- CREATE OR REPLACE lại đúng định nghĩa mới (không còn vendor_char) ở
    -- cuối script này.
    ALTER TABLE profile_cache DROP COLUMN vendor_char CASCADE;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS profile_led_code_cache (
  id BIGSERIAL PRIMARY KEY,
  profile_id INTEGER NOT NULL REFERENCES profile_cache(profile_id) ON DELETE CASCADE,
  led_slot INTEGER NOT NULL,
  led_code_id INTEGER,
  code_full TEXT NOT NULL,
  code_input TEXT,
  suffix_check TEXT NOT NULL,
  is_required BOOLEAN NOT NULL DEFAULT true,
  is_active BOOLEAN NOT NULL DEFAULT true,
  raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  synced_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT profile_led_code_cache_slot_between_1_2 CHECK (led_slot BETWEEN 1 AND 2),
  CONSTRAINT profile_led_code_cache_profile_slot_unique UNIQUE (profile_id, led_slot),
  CONSTRAINT profile_led_code_cache_profile_led_unique UNIQUE (profile_id, led_code_id)
);

-- Migration: đổi tên/nới rule constraint cũ (led_slot > 0) sang đúng nghiệp vụ
-- server (tối đa 2 LED code/profile) theo docs/11(2).md.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_schema = 'local_qr' AND table_name = 'profile_led_code_cache'
      AND constraint_name = 'profile_led_code_cache_slot_positive'
  ) THEN
    ALTER TABLE profile_led_code_cache DROP CONSTRAINT profile_led_code_cache_slot_positive;
    ALTER TABLE profile_led_code_cache
      ADD CONSTRAINT profile_led_code_cache_slot_between_1_2 CHECK (led_slot BETWEEN 1 AND 2);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS local_scan_records (
  id BIGSERIAL PRIMARY KEY,
  local_scan_id TEXT NOT NULL UNIQUE,
  machine_code TEXT NOT NULL,
  profile_id INTEGER REFERENCES profile_cache(profile_id) ON DELETE RESTRICT,
  profile_version INTEGER,
  duplicate_key TEXT,

  full_code_raw TEXT NOT NULL DEFAULT '',
  full_prefix TEXT,
  full_chassis_segment TEXT,
  full_chassis_code TEXT,
  full_before_vendor TEXT,
  full_vendor_char TEXT,
  full_led_code TEXT,
  full_factory_code TEXT,
  full_after_factory TEXT,
  chassis_scan_raw TEXT,
  full_code_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  led_scans_json JSONB NOT NULL DEFAULT '[]'::jsonb,

  local_status local_scan_status NOT NULL,
  local_ng_reason TEXT,

  server_code TEXT,
  server_message TEXT,
  server_scan_id INTEGER,
  server_first_scan_id INTEGER,
  server_status server_scan_status NOT NULL DEFAULT 'PENDING',

  final_status final_scan_status NOT NULL DEFAULT 'PENDING_SERVER',
  final_ng_reason TEXT,

  sync_status local_sync_status NOT NULL DEFAULT 'PENDING',
  sync_attempt_count INTEGER NOT NULL DEFAULT 0,
  last_sync_at TIMESTAMPTZ,
  next_retry_at TIMESTAMPTZ,
  last_error_code TEXT,
  last_error_message TEXT,

  scan_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS local_scan_led_items (
  id BIGSERIAL PRIMARY KEY,
  scan_id BIGINT NOT NULL REFERENCES local_scan_records(id) ON DELETE CASCADE,
  local_scan_id TEXT NOT NULL REFERENCES local_scan_records(local_scan_id) ON DELETE CASCADE,
  led_slot INTEGER NOT NULL,
  led_index INTEGER NOT NULL,
  led_scan_raw TEXT NOT NULL,
  led_lot_no TEXT,
  vendor_char TEXT,
  led_suffix TEXT,
  local_status local_scan_status NOT NULL,
  ng_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT local_scan_led_items_slot_positive CHECK (led_slot > 0),
  CONSTRAINT local_scan_led_items_index_positive CHECK (led_index > 0),
  CONSTRAINT local_scan_led_items_unique_item UNIQUE (scan_id, led_slot, led_index)
);

CREATE TABLE IF NOT EXISTS local_duplicate_keys (
  id BIGSERIAL PRIMARY KEY,
  profile_id INTEGER NOT NULL REFERENCES profile_cache(profile_id) ON DELETE CASCADE,
  duplicate_key TEXT NOT NULL,
  scope_key TEXT NOT NULL,
  first_local_scan_id TEXT REFERENCES local_scan_records(local_scan_id) ON DELETE SET NULL,
  first_scan_at TIMESTAMPTZ NOT NULL,
  machine_code TEXT,
  status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRED', 'IGNORED')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT local_duplicate_keys_unique_key UNIQUE (profile_id, duplicate_key, scope_key)
);

CREATE TABLE IF NOT EXISTS sync_batches (
  id BIGSERIAL PRIMARY KEY,
  batch_code TEXT NOT NULL UNIQUE,
  trigger_type sync_batch_trigger_type NOT NULL,
  total_sent INTEGER NOT NULL DEFAULT 0,
  total_ok INTEGER NOT NULL DEFAULT 0,
  total_ng INTEGER NOT NULL DEFAULT 0,
  total_failed INTEGER NOT NULL DEFAULT 0,
  server_batch_id INTEGER,
  server_code TEXT,
  server_message TEXT,
  status sync_batch_status NOT NULL DEFAULT 'PENDING',
  summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  response_json JSONB,
  error_message TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sync_batch_items (
  id BIGSERIAL PRIMARY KEY,
  batch_id BIGINT NOT NULL REFERENCES sync_batches(id) ON DELETE CASCADE,
  local_scan_id TEXT NOT NULL REFERENCES local_scan_records(local_scan_id) ON DELETE RESTRICT,
  result_success BOOLEAN NOT NULL DEFAULT false,
  result_code TEXT,
  result_message TEXT,
  server_scan_id INTEGER,
  final_status final_scan_status,
  ng_reason TEXT,
  response_json JSONB,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT sync_batch_items_unique_scan UNIQUE (batch_id, local_scan_id)
);

CREATE TABLE IF NOT EXISTS command_inbox (
  id BIGSERIAL PRIMARY KEY,
  server_command_id INTEGER NOT NULL UNIQUE,
  machine_code TEXT NOT NULL,
  command_type machine_command_type NOT NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  server_status TEXT,
  local_status command_local_status NOT NULL DEFAULT 'PENDING',
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  ack_sent_at TIMESTAMPTZ,
  ack_status command_ack_status,
  error_message TEXT,
  raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS local_notifications (
  id BIGSERIAL PRIMARY KEY,
  noti_code TEXT NOT NULL,
  severity local_notification_severity NOT NULL,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  status local_notification_status NOT NULL DEFAULT 'NEW',
  source local_notification_source NOT NULL DEFAULT 'LOCAL',
  related_local_scan_id TEXT REFERENCES local_scan_records(local_scan_id) ON DELETE SET NULL,
  related_batch_code TEXT REFERENCES sync_batches(batch_code) ON DELETE SET NULL,
  related_server_command_id INTEGER REFERENCES command_inbox(server_command_id) ON DELETE SET NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  read_at TIMESTAMPTZ,
  dismissed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS api_request_logs (
  id BIGSERIAL PRIMARY KEY,
  request_type TEXT NOT NULL,
  method api_request_method NOT NULL,
  url TEXT NOT NULL,
  local_scan_id TEXT REFERENCES local_scan_records(local_scan_id) ON DELETE SET NULL,
  batch_code TEXT REFERENCES sync_batches(batch_code) ON DELETE SET NULL,
  command_inbox_id BIGINT REFERENCES command_inbox(id) ON DELETE SET NULL,
  request_json JSONB,
  response_status_code INTEGER,
  response_json JSONB,
  result_code TEXT,
  success BOOLEAN NOT NULL DEFAULT false,
  error_message TEXT,
  duration_ms INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_event_logs (
  id BIGSERIAL PRIMARY KEY,
  level app_event_level NOT NULL DEFAULT 'INFO',
  event_code TEXT NOT NULL,
  message TEXT NOT NULL,
  payload_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION local_qr.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_id_counters_updated_at ON id_counters;
CREATE TRIGGER trg_id_counters_updated_at
BEFORE UPDATE ON id_counters
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_local_app_settings_updated_at ON local_app_settings;
CREATE TRIGGER trg_local_app_settings_updated_at
BEFORE UPDATE ON local_app_settings
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_server_settings_cache_updated_at ON server_settings_cache;
CREATE TRIGGER trg_server_settings_cache_updated_at
BEFORE UPDATE ON server_settings_cache
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_machine_cache_updated_at ON machine_cache;
CREATE TRIGGER trg_machine_cache_updated_at
BEFORE UPDATE ON machine_cache
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_vendor_cache_updated_at ON vendor_cache;
CREATE TRIGGER trg_vendor_cache_updated_at
BEFORE UPDATE ON vendor_cache
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_profile_cache_updated_at ON profile_cache;
CREATE TRIGGER trg_profile_cache_updated_at
BEFORE UPDATE ON profile_cache
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_profile_led_code_cache_updated_at ON profile_led_code_cache;
CREATE TRIGGER trg_profile_led_code_cache_updated_at
BEFORE UPDATE ON profile_led_code_cache
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_local_scan_records_updated_at ON local_scan_records;
CREATE TRIGGER trg_local_scan_records_updated_at
BEFORE UPDATE ON local_scan_records
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_local_scan_led_items_updated_at ON local_scan_led_items;
CREATE TRIGGER trg_local_scan_led_items_updated_at
BEFORE UPDATE ON local_scan_led_items
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_local_duplicate_keys_updated_at ON local_duplicate_keys;
CREATE TRIGGER trg_local_duplicate_keys_updated_at
BEFORE UPDATE ON local_duplicate_keys
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_sync_batches_updated_at ON sync_batches;
CREATE TRIGGER trg_sync_batches_updated_at
BEFORE UPDATE ON sync_batches
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_sync_batch_items_updated_at ON sync_batch_items;
CREATE TRIGGER trg_sync_batch_items_updated_at
BEFORE UPDATE ON sync_batch_items
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_command_inbox_updated_at ON command_inbox;
CREATE TRIGGER trg_command_inbox_updated_at
BEFORE UPDATE ON command_inbox
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

DROP TRIGGER IF EXISTS trg_local_notifications_updated_at ON local_notifications;
CREATE TRIGGER trg_local_notifications_updated_at
BEFORE UPDATE ON local_notifications
FOR EACH ROW EXECUTE FUNCTION local_qr.set_updated_at();

CREATE INDEX IF NOT EXISTS idx_machine_cache_active
  ON machine_cache (is_active, machine_code);

CREATE INDEX IF NOT EXISTS idx_vendor_cache_active
  ON vendor_cache (status, vendor_char);

CREATE INDEX IF NOT EXISTS idx_profile_cache_active
  ON profile_cache (is_active, profile_id);

CREATE INDEX IF NOT EXISTS idx_profile_led_code_cache_profile_slot
  ON profile_led_code_cache (profile_id, led_slot);

CREATE INDEX IF NOT EXISTS idx_local_scan_records_scan_at
  ON local_scan_records (scan_at DESC);

CREATE INDEX IF NOT EXISTS idx_local_scan_records_machine_scan_at
  ON local_scan_records (machine_code, scan_at DESC);

CREATE INDEX IF NOT EXISTS idx_local_scan_records_profile_duplicate
  ON local_scan_records (profile_id, duplicate_key, scan_at DESC);

CREATE INDEX IF NOT EXISTS idx_local_scan_records_sync_status
  ON local_scan_records (sync_status, next_retry_at);

CREATE INDEX IF NOT EXISTS idx_local_scan_records_pending_sync
  ON local_scan_records (sync_status, scan_at)
  WHERE sync_status IN ('PENDING', 'FAILED_RETRYABLE');

CREATE INDEX IF NOT EXISTS idx_local_scan_records_final_status
  ON local_scan_records (final_status, scan_at DESC);

CREATE INDEX IF NOT EXISTS idx_local_scan_records_ng_unreworked
  ON local_scan_records (scan_at DESC)
  WHERE local_status = 'NG' AND final_status = 'NG';

CREATE INDEX IF NOT EXISTS idx_local_scan_records_server_code
  ON local_scan_records (server_code, scan_at DESC);

CREATE INDEX IF NOT EXISTS idx_local_scan_led_items_local_scan_id
  ON local_scan_led_items (local_scan_id);

CREATE INDEX IF NOT EXISTS idx_local_duplicate_keys_lookup
  ON local_duplicate_keys (profile_id, duplicate_key, scope_key, status);

CREATE INDEX IF NOT EXISTS idx_sync_batches_status
  ON sync_batches (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_sync_batch_items_scan
  ON sync_batch_items (local_scan_id);

CREATE INDEX IF NOT EXISTS idx_command_inbox_status
  ON command_inbox (local_status, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_command_inbox_type
  ON command_inbox (command_type, local_status);

CREATE INDEX IF NOT EXISTS idx_local_notifications_status
  ON local_notifications (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_api_request_logs_type_time
  ON api_request_logs (request_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_api_request_logs_scan
  ON api_request_logs (local_scan_id);

CREATE INDEX IF NOT EXISTS idx_app_event_logs_code_time
  ON app_event_logs (event_code, created_at DESC);

CREATE OR REPLACE VIEW v_pending_sync_scans AS
SELECT
  id,
  local_scan_id,
  machine_code,
  profile_id,
  duplicate_key,
  local_status,
  final_status,
  sync_status,
  sync_attempt_count,
  next_retry_at,
  scan_at
FROM local_scan_records
WHERE sync_status IN ('PENDING', 'FAILED_RETRYABLE')
ORDER BY scan_at ASC;

CREATE OR REPLACE VIEW v_active_profiles AS
SELECT
  p.profile_id,
  p.version,
  p.chassis_code_full,
  p.factory_code,
  p.full_code_length,
  p.full_vendor_position,
  p.led_scan_length,
  p.led_vendor_position,
  p.synced_at,
  COUNT(l.id) AS led_code_count
FROM profile_cache p
LEFT JOIN profile_led_code_cache l
  ON l.profile_id = p.profile_id
 AND l.is_active = true
WHERE p.is_active = true
GROUP BY
  p.profile_id,
  p.version,
  p.chassis_code_full,
  p.factory_code,
  p.full_code_length,
  p.full_vendor_position,
  p.led_scan_length,
  p.led_vendor_position,
  p.synced_at;

CREATE OR REPLACE VIEW v_today_scan_summary AS
SELECT
  CURRENT_DATE AS scan_date,
  COUNT(*) AS total_scan,
  COUNT(*) FILTER (WHERE local_status = 'OK') AS local_ok,
  COUNT(*) FILTER (WHERE local_status = 'NG') AS local_ng,
  COUNT(*) FILTER (WHERE final_status = 'OK') AS final_ok,
  COUNT(*) FILTER (WHERE final_status = 'NG') AS final_ng,
  COUNT(*) FILTER (WHERE sync_status IN ('PENDING', 'FAILED_RETRYABLE', 'SYNCING')) AS pending_sync
FROM local_scan_records
WHERE scan_at >= date_trunc('day', now());

CREATE OR REPLACE VIEW v_latest_notifications AS
SELECT
  id,
  noti_code,
  severity,
  title,
  message,
  status,
  source,
  related_local_scan_id,
  related_batch_code,
  related_server_command_id,
  created_at
FROM local_notifications
ORDER BY created_at DESC
LIMIT 100;

CREATE OR REPLACE VIEW v_local_runtime_status AS
SELECT
  id,
  server_host,
  api_port,
  machine_code,
  machine_serial,
  machine_uid,
  registration_request_id,
  registration_status,
  license_activated_at,
  server_online,
  local_runtime_status,
  local_status_message,
  local_status_updated_at,
  active_profile_id,
  last_health_at,
  last_config_sync_at,
  last_heartbeat_at,
  last_server_error_code,
  last_server_error_message,
  updated_at
FROM local_app_settings
WHERE id = 1;

-- Seed dòng singleton (id=1) — mọi cột NOT NULL đều có DEFAULT nên chỉ cần
-- insert id, phần còn lại tự điền đúng giá trị mặc định của schema. Thiếu
-- bước này thì local_app_settings/server_settings_cache trống hoàn toàn sau
-- khi cài mới (schema.sql chỉ CREATE TABLE, không tự sinh dòng) — mọi
-- update_app_settings()/get_app_settings() sau đó đều vô hiệu lặng lẽ (UPDATE
-- không khớp WHERE id = 1 nào, không báo lỗi), gây ra hàng loạt triệu chứng
-- khó truy: máy được server APPROVED nhưng Register không hiện trạng thái,
-- heartbeat gửi machine_code=NULL bị server từ chối "machine_code must be a
-- string", v.v. ON CONFLICT DO NOTHING để chạy lại schema.sql trên DB đã có
-- dữ liệu không bị ghi đè cấu hình hiện tại.
INSERT INTO local_app_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
INSERT INTO server_settings_cache (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

INSERT INTO schema_migrations (version, name)
VALUES ('20260713_001', 'initial_local_postgres_schema')
ON CONFLICT (version) DO NOTHING;

COMMIT;
