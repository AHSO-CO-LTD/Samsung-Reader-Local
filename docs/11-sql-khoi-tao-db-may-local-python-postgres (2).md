# SQL khởi tạo database máy local Python dùng PostgreSQL

Tài liệu này dành cho người code chương trình máy local Python. Mục tiêu là cung cấp một bộ lệnh SQL đầy đủ để copy vào Query Tool của PostgreSQL và tạo toàn bộ database local một lần.

Quan trọng: đây là database của máy local, không phải database server chính của app `Samsung_QR_Recorder_Server`.

## 1. Phạm vi

Database local dùng để:

- Lưu cấu hình kết nối server.
- Cache cấu hình máy, profile, chassis code, LED code từ server.
- Lưu bản ghi scan local trước khi gửi server.
- Lưu bản ghi pending sync khi mất mạng hoặc server tạm offline.
- Lưu command nhận từ server qua polling.
- Lưu notification local để UI Python hiển thị rõ trạng thái.
- Lưu log request API và log sự kiện local để truy vết lỗi.

Database local không dùng để:

- Quản lý user đăng nhập server.
- Chỉnh sửa master data chính thức.
- Thay thế rule duplicate của server.
- Lưu bảng phiên runtime WebSocket của server. Phiên chạy realtime được server tự tạo và lưu ở database server.
- Tự ghi trực tiếp vào database server chính.

## 2. Giả định PostgreSQL

Script này dùng cho PostgreSQL 13 trở lên.

Thông tin mặc định trong tài liệu:

```txt
Database name : samsung_qr_local
Schema        : local_qr
User          : samsung_qr_local_user
API port      : 3979
Machine code  : LOCAL01
```

Nếu máy local đã có database/user riêng, chỉ cần sửa các giá trị này trước khi chạy.

## 3. Cách chạy trong Query Tool

### 3.1. Nếu chưa có database local

Kết nối vào database quản trị, thường là `postgres`, rồi chạy block này trước.

Nếu database hoặc user đã tồn tại, bỏ qua block này hoặc sửa theo môi trường thật.

```sql
CREATE ROLE samsung_qr_local_user LOGIN PASSWORD 'ChangeMe_Use_Strong_Local_Password';

CREATE DATABASE samsung_qr_local
  WITH OWNER = samsung_qr_local_user
       ENCODING = 'UTF8'
       CONNECTION LIMIT = -1;

GRANT ALL PRIVILEGES ON DATABASE samsung_qr_local TO samsung_qr_local_user;
```

### 3.2. Tạo toàn bộ schema local

Kết nối vào database `samsung_qr_local`, sau đó copy toàn bộ block SQL ở mục 4 và chạy một lần.

Script chính có đặc điểm:

- Dùng schema riêng `local_qr`.
- Dùng `CREATE TABLE IF NOT EXISTS`.
- Không có `DROP TABLE`.
- Có enum, bảng, index, trigger `updated_at`, view và seed dữ liệu mặc định.
- Có thể chạy lại để bổ sung phần còn thiếu mà không xóa dữ liệu scan.

## 4. SQL tạo toàn bộ database local PostgreSQL

```sql
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

-- Nghiệp vụ server: mỗi profile chỉ được gắn tối đa 2 LED code.

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

INSERT INTO schema_migrations (version, name)
VALUES ('20260713_001', 'initial_local_postgres_schema')
ON CONFLICT (version) DO NOTHING;

INSERT INTO local_app_settings (
  id,
  server_host,
  api_port,
  machine_code,
  machine_serial,
  machine_uid,
  machine_license_key,
  registration_status,
  app_version,
  local_db_version,
  duplicate_scope,
  server_online,
  local_runtime_status,
  local_status_message,
  local_status_updated_at
)
VALUES (
  1,
  '127.0.0.1',
  3979,
  'LOCAL01',
  'SN-LOCAL01-DEV',
  'UID-LOCAL01-DEV',
  'SN-LOCAL01-DEV|UID-LOCAL01-DEV',
  'APPROVED',
  '1.0.0',
  '20260713.001',
  'DAY',
  false,
  'READY',
  'Máy local mẫu đã được định danh sẵn. Hãy sửa serial, uid, license key và machine_code trước khi chạy thật.',
  now()
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO server_settings_cache (
  id,
  factory_code_default,
  full_code_length_default,
  full_vendor_position_default,
  led_scan_length_default,
  led_vendor_position_default,
  duplicate_days,
  heartbeat_timeout_seconds
)
VALUES (
  1,
  'DZLV',
  35,
  18,
  22,
  16,
  30,
  60
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO id_counters (counter_name, counter_date, current_value)
VALUES
  ('local_scan_sequence', CURRENT_DATE, 0),
  ('batch_sequence', CURRENT_DATE, 0)
ON CONFLICT (counter_name, counter_date) DO NOTHING;

COMMIT;
```

<!-- LOCAL_DB_FIELD_GUIDE_START -->
## 4.1. Giải thích toàn bộ bảng và field local

Mục này giải thích riêng database của máy local Python. Tất cả bảng và field bên dưới được lấy trực tiếp từ block SQL ở mục 4, vì vậy đội local chỉ cần đọc phần này để hiểu field nào tồn tại, vì sao cần field đó và app nên dùng field đó ở bước nào.

Tổng quan field hiện tại: 17 bảng, 236 field, 15 enum và 5 view.

| Nhóm | Bảng | Số field | Vai trò |
| --- | --- | --- | --- |
| Nền tảng vận hành local | `schema_migrations` | 3 | Ghi nhận version migration đã áp dụng cho database local để biết máy đang ở schema nào. |
| Nền tảng vận hành local | `id_counters` | 4 | Cấp sequence theo ngày cho local_scan_id và batch_code, dùng an toàn trong transaction khi app có nhiều luồng. |
| Nền tảng vận hành local | `local_app_settings` | 25 | Bảng cấu hình trung tâm của app local. Chỉ một dòng id = 1, lưu server, định danh máy, trạng thái runtime và các mốc sync. |
| Cache dữ liệu từ server | `server_settings_cache` | 12 | Cache server settings tải từ API config: rule độ dài code, vị trí vendor, duplicate window và heartbeat timeout. |
| Cache dữ liệu từ server | `machine_cache` | 13 | Cache thông tin chính máy local sau khi server định danh: mã máy, serial, uid, line, station, IP và active state. |
| Cache dữ liệu từ server | `vendor_cache` | 8 | Cache danh sách vendor active từ server. Vendor không còn nằm cố định trong profile; local lấy vendor từ ký tự thứ 18 của full code rồi tra bảng này. |
| Cache dữ liệu từ server | `profile_cache` | 15 | Cache profile active từ server để local parse full code, kiểm factory, chassis, LED và chọn mã hàng chạy. |
| Cache dữ liệu từ server | `profile_led_code_cache` | 13 | Cache tối đa 2 LED code/slot thuộc từng profile để local kiểm LED scan theo slot và suffix. |
| Scan, LED và duplicate local | `local_scan_records` | 36 | Bảng scan chính của máy local. Mỗi lượt scan phải lưu tại đây trước khi gọi server để retry giữ nguyên local_scan_id. |
| Scan, LED và duplicate local | `local_scan_led_items` | 13 | Chi tiết từng LED item trong một scan local, dùng truy vết lỗi LED và tạo manifest khi reconcile. |
| Scan, LED và duplicate local | `local_duplicate_keys` | 10 | Duplicate cục bộ của máy local theo profile và scope, chỉ dùng cảnh báo local, không thay duplicate nhiều ngày của server. |
| Sync offline và reconcile | `sync_batches` | 19 | Header batch sync khi local gửi các scan pending/offline lên server. |
| Sync offline và reconcile | `sync_batch_items` | 13 | Kết quả từng scan nằm trong batch sync để biết record nào OK, NG, fail hoặc cần retry. |
| Command, thông báo và log | `command_inbox` | 16 | Inbox command server gửi qua polling. Local lưu command, xử lý rồi ack/fail lại server. |
| Command, thông báo và log | `local_notifications` | 15 | Thông báo nội bộ cho UI Python local, khác với notification_events của server UI. |
| Command, thông báo và log | `api_request_logs` | 15 | Log request/response khi local gọi API server, phục vụ debug máy local đã gửi gì và server trả gì. |
| Command, thông báo và log | `app_event_logs` | 6 | Log sự kiện runtime nội bộ của app local như boot, parse lỗi, DB lỗi, reconnect hoặc worker crash. |

### Nền tảng vận hành local

#### `schema_migrations`

Ghi nhận version migration đã áp dụng cho database local để biết máy đang ở schema nào.

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `version` | `TEXT` | Có | - | `PK` | Version/schema/migration hoặc version profile tùy bảng. | Cần lưu version vì Version/schema/migration hoặc version profile tùy bảng. Field này hỗ trợ kiểm soát version schema local khi cài mới hoặc nâng cấp DB.. | Migration tool ghi sau khi chạy script; app đọc khi nâng cấp để biết version nào đã áp dụng. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `name` | `TEXT` | Có | - | `NOT NULL` | Tên mô tả ngắn của bản ghi. | Cần lưu name vì Tên mô tả ngắn của bản ghi. Field này hỗ trợ kiểm soát version schema local khi cài mới hoặc nâng cấp DB.. | Migration tool ghi sau khi chạy script; app đọc khi nâng cấp để biết version nào đã áp dụng. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `applied_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm migration được ghi nhận đã áp dụng. | Cần mốc thời gian cho applied at để truy vết, sắp xếp hoặc tính retry/timeout. | Migration tool ghi sau khi chạy script; app đọc khi nâng cấp để biết version nào đã áp dụng. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |

#### `id_counters`

Cấp sequence theo ngày cho local_scan_id và batch_code, dùng an toàn trong transaction khi app có nhiều luồng.

**Ràng buộc/chỉ mục chính:**

- `PRIMARY KEY (counter_name, counter_date)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `counter_name` | `TEXT` | Có | - | `NOT NULL` | Tên bộ đếm, ví dụ local_scan_sequence hoặc batch_sequence. | Cần lưu counter name vì Tên bộ đếm, ví dụ local_scan_sequence hoặc batch_sequence. Field này hỗ trợ cấp số tuần tự an toàn cho local_scan_id, batch_code hoặc các mã local khác.. | App đọc và update trong transaction khi cần sinh mã mới; không sửa tay trong lúc máy đang chạy. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `counter_date` | `DATE` | Có | `CURRENT_DATE` | `NOT NULL`<br>`DEFAULT CURRENT_DATE` | Ngày áp dụng bộ đếm. Sequence thường reset theo ngày. | Cần lưu counter date vì Ngày áp dụng bộ đếm. Sequence thường reset theo ngày. Field này hỗ trợ cấp số tuần tự an toàn cho local_scan_id, batch_code hoặc các mã local khác.. | App đọc và update trong transaction khi cần sinh mã mới; không sửa tay trong lúc máy đang chạy. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `CURRENT_DATE`. |
| `current_value` | `BIGINT` | Có | `0` | `NOT NULL`<br>`DEFAULT 0` | Giá trị sequence hiện tại. | Cần lưu current value vì Giá trị sequence hiện tại. Field này hỗ trợ cấp số tuần tự an toàn cho local_scan_id, batch_code hoặc các mã local khác.. | App đọc và update trong transaction khi cần sinh mã mới; không sửa tay trong lúc máy đang chạy. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `0`. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App đọc và update trong transaction khi cần sinh mã mới; không sửa tay trong lúc máy đang chạy. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

#### `local_app_settings`

Bảng cấu hình trung tâm của app local. Chỉ một dòng id = 1, lưu server, định danh máy, trạng thái runtime và các mốc sync.

**Ràng buộc/chỉ mục chính:**

- `CONSTRAINT local_app_settings_single_row CHECK (id = 1)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `SMALLINT` | Có | `1` | `PK`<br>`DEFAULT 1` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `server_host` | `TEXT` | Có | `'127.0.0.1'` | `NOT NULL`<br>`DEFAULT '127.0.0.1'` | IP hoặc hostname của máy server mà local gọi API. | Cần lưu server host vì IP hoặc hostname của máy server mà local gọi API. Field này hỗ trợ lưu cấu hình vận hành và trạng thái định danh của đúng máy local này.. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `'127.0.0.1'`. |
| `api_port` | `INTEGER` | Có | `3979` | `NOT NULL`<br>`CHECK`<br>`DEFAULT 3979` | Port API server, mặc định 3979. | Cần lưu api port vì Port API server, mặc định 3979. Field này hỗ trợ lưu cấu hình vận hành và trạng thái định danh của đúng máy local này.. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `3979`. |
| `machine_code` | `TEXT` | Có | `'LOCAL01'` | `NOT NULL`<br>`DEFAULT 'LOCAL01'` | Mã máy local chính thức sau khi server định danh. | Cần mã nghiệp vụ machine code để đối chiếu với rule/server và hiển thị cho người vận hành. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `'LOCAL01'`. |
| `machine_serial` | `TEXT` | Không | - | - | Serial phần cứng ổn định của máy local, thường lấy từ mainboard. | Cần serial phần cứng ổn định để máy local tự nhận diện với server ngay từ lúc chưa có machine_code. | Lấy từ mainboard/hardware khi app khởi động; gửi trong register, get config, sync và websocket. |
| `machine_uid` | `TEXT` | Không | - | - | UID ổn định của app/máy local, dùng cùng serial để định danh. | Cần UID ổn định của app/máy để kết hợp với serial thành danh tính local. | Sinh/lấy từ định danh app local; gửi kèm serial trong các API định danh máy. |
| `machine_license_key` | `TEXT` | Không | - | - | Raw license local muốn lưu để đối chiếu; flow hiện tại có thể là serial + uid. | Cần lưu raw license hiện tại để sau này thay bằng công thức mã hóa mà không đổi schema. | Hiện lưu raw key; sau này thay logic decode/verify nhưng app vẫn đọc/ghi cùng field. |
| `registration_request_id` | `TEXT` | Không | - | - | Request ID server trả khi local gửi register-request. | Cần ID tham chiếu registration request id để nối dữ liệu giữa các bảng hoặc với server. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `registration_status` | `TEXT` | Có | `'NOT_REQUESTED'` | `NOT NULL`<br>`CHECK`<br>`DEFAULT 'NOT_REQUESTED'` | Trạng thái định danh local: NOT_REQUESTED, PENDING, APPROVED, REJECTED hoặc DUPLICATE. | Cần trạng thái registration status để app biết bước xử lý hiện tại và quyết định retry/hiển thị. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `license_activated_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm server đã import/kích hoạt license cho request này, nếu có. | Cần mốc thời gian cho license activated at để truy vết, sắp xếp hoặc tính retry/timeout. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `active_profile_id` | `INTEGER` | Không | - | - | Profile đang được chọn để chạy trên local. | Cần ID tham chiếu active profile id để nối dữ liệu giữa các bảng hoặc với server. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `app_version` | `TEXT` | Không | - | - | Version app Python local đang chạy. | Cần lưu app version vì Version app Python local đang chạy. Field này hỗ trợ lưu cấu hình vận hành và trạng thái định danh của đúng máy local này.. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `local_db_version` | `TEXT` | Có | `'20260713.001'` | `NOT NULL`<br>`DEFAULT '20260713.001'` | Version schema/data local DB hiện tại. | Cần lưu local db version vì Version schema/data local DB hiện tại. Field này hỗ trợ lưu cấu hình vận hành và trạng thái định danh của đúng máy local này.. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `'20260713.001'`. |
| `duplicate_scope` | `duplicate_local_scope` | Có | `'DAY'` | `NOT NULL`<br>`DEFAULT 'DAY'` | Scope duplicate cục bộ mà local đang dùng. | Cần lưu duplicate scope vì Scope duplicate cục bộ mà local đang dùng. Field này hỗ trợ lưu cấu hình vận hành và trạng thái định danh của đúng máy local này.. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `'DAY'`. |
| `server_online` | `BOOLEAN` | Có | `false` | `NOT NULL`<br>`DEFAULT false` | Kết quả kiểm tra kết nối server gần nhất. | Cần lưu server online vì Kết quả kiểm tra kết nối server gần nhất. Field này hỗ trợ lưu cấu hình vận hành và trạng thái định danh của đúng máy local này.. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `false`. |
| `local_runtime_status` | `TEXT` | Có | `'BOOTING'` | `NOT NULL`<br>`CHECK`<br>`DEFAULT 'BOOTING'` | Trạng thái tổng hợp cho UI local: BOOTING, READY, SCANNING, SYNCING, BLOCKED... | Cần trạng thái local runtime status để app biết bước xử lý hiện tại và quyết định retry/hiển thị. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `local_status_message` | `TEXT` | Không | - | - | Thông điệp ngắn giải thích trạng thái hiện tại cho người vận hành. | Cần thông điệp local status message để giải thích kết quả cho UI hoặc log. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `local_status_updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật trạng thái UI local gần nhất. | Cần mốc thời gian cho local status updated at để truy vết, sắp xếp hoặc tính retry/timeout. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `last_health_at` | `TIMESTAMPTZ` | Không | - | - | Lần cuối local kiểm tra health/kết nối server thành công. | Cần mốc thời gian cho last health at để truy vết, sắp xếp hoặc tính retry/timeout. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `last_config_sync_at` | `TIMESTAMPTZ` | Không | - | - | Lần cuối local tải cấu hình/profile từ server. | Cần mốc thời gian cho last config sync at để truy vết, sắp xếp hoặc tính retry/timeout. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `last_heartbeat_at` | `TIMESTAMPTZ` | Không | - | - | Lần cuối local gửi heartbeat thành công. | Cần mốc thời gian cho last heartbeat at để truy vết, sắp xếp hoặc tính retry/timeout. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `last_server_error_code` | `TEXT` | Không | - | - | Mã lỗi server gần nhất local nhận được. | Cần mã nghiệp vụ last server error code để đối chiếu với rule/server và hiển thị cho người vận hành. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Ghi đè bằng giá trị mới nhất; dùng để hiển thị tình trạng hiện tại. |
| `last_server_error_message` | `TEXT` | Không | - | - | Thông điệp lỗi server gần nhất local nhận được. | Cần thông điệp last server error message để giải thích kết quả cho UI hoặc log. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Ghi đè bằng giá trị mới nhất; dùng để hiển thị tình trạng hiện tại. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App đọc khi startup, cập nhật sau register/config/heartbeat và dùng để hiển thị trạng thái local. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

### Cache dữ liệu từ server

#### `server_settings_cache`

Cache server settings tải từ API config: rule độ dài code, vị trí vendor, duplicate window và heartbeat timeout.

**Ràng buộc/chỉ mục chính:**

- `CONSTRAINT server_settings_cache_single_row CHECK (id = 1)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `SMALLINT` | Có | `1` | `PK`<br>`DEFAULT 1` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `factory_code_default` | `TEXT` | Có | `'DZLV'` | `NOT NULL`<br>`DEFAULT 'DZLV'` | Factory code mặc định dùng khi validate full code. | Cần lưu factory code default vì Factory code mặc định dùng khi validate full code. Field này hỗ trợ giữ bản cache cấu hình server để local vẫn validate được khi mất mạng.. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `'DZLV'`. |
| `full_code_length_default` | `INTEGER` | Có | `35` | `NOT NULL`<br>`DEFAULT 35` | Độ dài full code mặc định. | Cần lưu full code length default vì Độ dài full code mặc định. Field này hỗ trợ giữ bản cache cấu hình server để local vẫn validate được khi mất mạng.. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `35`. |
| `full_vendor_position_default` | `INTEGER` | Có | `18` | `NOT NULL`<br>`DEFAULT 18` | Vị trí ký tự vendor trong full code mặc định. | Cần lưu full vendor position default vì Vị trí ký tự vendor trong full code mặc định. Field này hỗ trợ giữ bản cache cấu hình server để local vẫn validate được khi mất mạng.. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `18`. |
| `led_scan_length_default` | `INTEGER` | Có | `22` | `NOT NULL`<br>`DEFAULT 22` | Độ dài LED scan mặc định. | Cần lưu led scan length default vì Độ dài LED scan mặc định. Field này hỗ trợ giữ bản cache cấu hình server để local vẫn validate được khi mất mạng.. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `22`. |
| `led_vendor_position_default` | `INTEGER` | Có | `16` | `NOT NULL`<br>`DEFAULT 16` | Vị trí ký tự vendor trong LED scan mặc định. | Cần lưu led vendor position default vì Vị trí ký tự vendor trong LED scan mặc định. Field này hỗ trợ giữ bản cache cấu hình server để local vẫn validate được khi mất mạng.. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `16`. |
| `duplicate_days` | `INTEGER` | Có | `30` | `NOT NULL`<br>`DEFAULT 30` | Số ngày server dùng để kiểm duplicate; local lưu để hiển thị/đồng bộ rule. | Cần lưu duplicate days vì Số ngày server dùng để kiểm duplicate; local lưu để hiển thị/đồng bộ rule. Field này hỗ trợ giữ bản cache cấu hình server để local vẫn validate được khi mất mạng.. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `30`. |
| `heartbeat_timeout_seconds` | `INTEGER` | Có | `60` | `NOT NULL`<br>`DEFAULT 60` | Ngưỡng timeout heartbeat server cấu hình. | Cần lưu heartbeat timeout seconds vì Ngưỡng timeout heartbeat server cấu hình. Field này hỗ trợ giữ bản cache cấu hình server để local vẫn validate được khi mất mạng.. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `60`. |
| `raw_json` | `JSONB` | Có | `'{}'::jsonb` | `NOT NULL`<br>`DEFAULT '{}'::jsonb` | JSON gốc nhận từ server/API để đối chiếu khi cần debug. | Cần giữ payload gốc để đối chiếu khi mapping field bị sai hoặc server đổi format. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `synced_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm dữ liệu được sync/cache từ server. | Cần mốc sync để biết dữ liệu cache này lấy từ server ở thời điểm nào. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. Không có default nên app phải tự set khi nghiệp vụ cần. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App upsert sau khi gọi API lấy config; màn hình vận hành và validator đọc cache này. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

#### `machine_cache`

Cache thông tin chính máy local sau khi server định danh: mã máy, serial, uid, line, station, IP và active state.

**Ràng buộc/chỉ mục chính:**

- `CREATE INDEX IF NOT EXISTS idx_machine_cache_active ON machine_cache (is_active, machine_code)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `machine_code` | `TEXT` | Có | - | `PK` | Mã máy local chính thức sau khi server định danh. | Cần mã nghiệp vụ machine code để đối chiếu với rule/server và hiển thị cho người vận hành. | App upsert khi server trả thông tin máy; startup/config/status đọc lại theo serial + uid. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `server_machine_id` | `INTEGER` | Không | - | - | ID máy trên database server, nếu API trả về. | Cần ID tham chiếu server machine id để nối dữ liệu giữa các bảng hoặc với server. | App upsert khi server trả thông tin máy; startup/config/status đọc lại theo serial + uid. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `machine_name` | `TEXT` | Có | - | `NOT NULL` | Tên máy local hiển thị trên server/UI. | Cần lưu machine name vì Tên máy local hiển thị trên server/UI. Field này hỗ trợ giữ thông tin máy đã được server duyệt để local không phụ thuộc vào machine_code khi khởi động.. | App upsert khi server trả thông tin máy; startup/config/status đọc lại theo serial + uid. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `serial` | `TEXT` | Không | - | - | Serial đã được server duyệt cho máy này. | Cần lưu serial server đã duyệt để đối chiếu với serial thật của máy khi startup. | Upsert từ response server; khi startup so với serial phần cứng để phát hiện sai máy. |
| `uid` | `TEXT` | Không | - | - | UID đã được server duyệt cho máy này. | Cần lưu UID server đã duyệt để tránh máy khác dùng nhầm cache định danh. | Upsert từ response server; dùng cùng serial để lấy config và xác nhận đúng máy. |
| `line_name` | `TEXT` | Không | - | - | Tên line sản xuất của máy. | Cần lưu line name vì Tên line sản xuất của máy. Field này hỗ trợ giữ thông tin máy đã được server duyệt để local không phụ thuộc vào machine_code khi khởi động.. | App upsert khi server trả thông tin máy; startup/config/status đọc lại theo serial + uid. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `station_name` | `TEXT` | Không | - | - | Tên station/trạm của máy. | Cần lưu station name vì Tên station/trạm của máy. Field này hỗ trợ giữ thông tin máy đã được server duyệt để local không phụ thuộc vào machine_code khi khởi động.. | App upsert khi server trả thông tin máy; startup/config/status đọc lại theo serial + uid. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `ip_address` | `TEXT` | Không | - | - | IP cấu hình hoặc IP đã biết của máy local. | Cần lưu ip address vì IP cấu hình hoặc IP đã biết của máy local. Field này hỗ trợ giữ thông tin máy đã được server duyệt để local không phụ thuộc vào machine_code khi khởi động.. | App upsert khi server trả thông tin máy; startup/config/status đọc lại theo serial + uid. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `is_active` | `BOOLEAN` | Có | `true` | `NOT NULL`<br>`DEFAULT true` | Bản ghi còn active và được local sử dụng hay không. | Cần cờ bật/tắt để giữ lịch sử nhưng không cho app sử dụng bản ghi đã ngừng hiệu lực. | App upsert khi server trả thông tin máy; startup/config/status đọc lại theo serial + uid. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `true`. |
| `raw_json` | `JSONB` | Có | `'{}'::jsonb` | `NOT NULL`<br>`DEFAULT '{}'::jsonb` | JSON gốc nhận từ server/API để đối chiếu khi cần debug. | Cần giữ payload gốc để đối chiếu khi mapping field bị sai hoặc server đổi format. | App upsert khi server trả thông tin máy; startup/config/status đọc lại theo serial + uid. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `synced_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm dữ liệu được sync/cache từ server. | Cần mốc sync để biết dữ liệu cache này lấy từ server ở thời điểm nào. | App upsert khi server trả thông tin máy; startup/config/status đọc lại theo serial + uid. Không có default nên app phải tự set khi nghiệp vụ cần. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App upsert khi server trả thông tin máy; startup/config/status đọc lại theo serial + uid. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App upsert khi server trả thông tin máy; startup/config/status đọc lại theo serial + uid. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

#### `vendor_cache`

Cache danh sách vendor active từ server. Vendor không còn nằm cố định trong profile; local lấy vendor từ ký tự thứ 18 của full code rồi tra bảng này.

**Ràng buộc/chỉ mục chính:**

- `CREATE INDEX IF NOT EXISTS idx_vendor_cache_active ON vendor_cache (status, vendor_char)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `vendor_id` | `INTEGER` | Không | - | - | ID vendor trên server, nếu có. | Cần ID tham chiếu vendor id để nối dữ liệu giữa các bảng hoặc với server. | App upsert từ data.vendors của API config; validator đọc theo vendor_char khi parse full code. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `vendor_name` | `TEXT` | Có | - | `NOT NULL` | Tên vendor hiển thị. | Cần lưu vendor name vì Tên vendor hiển thị. Field này hỗ trợ giữ danh sách vendor active để local tra cứu ký tự vendor parse từ full code.. | App upsert từ data.vendors của API config; validator đọc theo vendor_char khi parse full code. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `vendor_char` | `TEXT` | Có | - | `PK` | Ký tự vendor hợp lệ trong full code và LED scan. | Cần lưu vendor char vì Ký tự vendor hợp lệ trong full code và LED scan. Field này hỗ trợ giữ danh sách vendor active để local tra cứu ký tự vendor parse từ full code.. | App upsert từ data.vendors của API config; validator đọc theo vendor_char khi parse full code. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `status` | `TEXT` | Có | `'ACTIVE'` | `NOT NULL`<br>`CHECK`<br>`DEFAULT 'ACTIVE'` | Trạng thái hiện tại của bản ghi. | Cần trạng thái tổng quát để lọc bản ghi active/inactive hoặc đang xử lý. | App upsert từ data.vendors của API config; validator đọc theo vendor_char khi parse full code. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `raw_json` | `JSONB` | Có | `'{}'::jsonb` | `NOT NULL`<br>`DEFAULT '{}'::jsonb` | JSON gốc nhận từ server/API để đối chiếu khi cần debug. | Cần giữ payload gốc để đối chiếu khi mapping field bị sai hoặc server đổi format. | App upsert từ data.vendors của API config; validator đọc theo vendor_char khi parse full code. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `synced_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm dữ liệu được sync/cache từ server. | Cần mốc sync để biết dữ liệu cache này lấy từ server ở thời điểm nào. | App upsert từ data.vendors của API config; validator đọc theo vendor_char khi parse full code. Không có default nên app phải tự set khi nghiệp vụ cần. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App upsert từ data.vendors của API config; validator đọc theo vendor_char khi parse full code. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App upsert từ data.vendors của API config; validator đọc theo vendor_char khi parse full code. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

#### `profile_cache`

Cache profile active từ server để local parse full code, kiểm factory, chassis, LED và chọn mã hàng chạy.

**Ràng buộc/chỉ mục chính:**

- `CREATE INDEX IF NOT EXISTS idx_profile_cache_active ON profile_cache (is_active, profile_id)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `profile_id` | `INTEGER` | Có | - | `PK` | ID profile liên quan. | Cần liên kết dữ liệu với profile/mã hàng đang chạy để validate và thống kê chính xác. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `version` | `INTEGER` | Có | `1` | `NOT NULL`<br>`DEFAULT 1` | Version/schema/migration hoặc version profile tùy bảng. | Cần lưu version vì Version/schema/migration hoặc version profile tùy bảng. Field này hỗ trợ giữ danh sách mã hàng/profile mà máy local được phép chọn và chạy.. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `1`. |
| `chassis_code_id` | `INTEGER` | Không | - | - | ID chassis code trên server, nếu có. | Cần ID tham chiếu chassis code id để nối dữ liệu giữa các bảng hoặc với server. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `chassis_code_full` | `TEXT` | Có | - | `NOT NULL` | Mã chassis đầy đủ dùng để validate full/chassis scan. | Cần lưu chassis code full vì Mã chassis đầy đủ dùng để validate full/chassis scan. Field này hỗ trợ giữ danh sách mã hàng/profile mà máy local được phép chọn và chạy.. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `chassis_code_input` | `TEXT` | Không | - | - | Mã chassis dạng input/ngắn nếu server có. | Cần lưu chassis code input vì Mã chassis dạng input/ngắn nếu server có. Field này hỗ trợ giữ danh sách mã hàng/profile mà máy local được phép chọn và chạy.. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `factory_code` | `TEXT` | Có | - | `NOT NULL` | Factory code hợp lệ của profile. | Cần mã nghiệp vụ factory code để đối chiếu với rule/server và hiển thị cho người vận hành. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `full_code_length` | `INTEGER` | Có | `35` | `NOT NULL`<br>`DEFAULT 35` | Độ dài full code áp dụng cho profile này. | Cần lưu full code length vì Độ dài full code áp dụng cho profile này. Field này hỗ trợ giữ danh sách mã hàng/profile mà máy local được phép chọn và chạy.. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `35`. |
| `full_vendor_position` | `INTEGER` | Có | `18` | `NOT NULL`<br>`DEFAULT 18` | Vị trí vendor trong full code áp dụng cho profile này. | Cần lưu full vendor position vì Vị trí vendor trong full code áp dụng cho profile này. Field này hỗ trợ giữ danh sách mã hàng/profile mà máy local được phép chọn và chạy.. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `18`. |
| `led_scan_length` | `INTEGER` | Có | `22` | `NOT NULL`<br>`DEFAULT 22` | Độ dài LED scan áp dụng cho profile này. | Cần lưu led scan length vì Độ dài LED scan áp dụng cho profile này. Field này hỗ trợ giữ danh sách mã hàng/profile mà máy local được phép chọn và chạy.. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `22`. |
| `led_vendor_position` | `INTEGER` | Có | `16` | `NOT NULL`<br>`DEFAULT 16` | Vị trí vendor trong LED scan áp dụng cho profile này. | Cần lưu led vendor position vì Vị trí vendor trong LED scan áp dụng cho profile này. Field này hỗ trợ giữ danh sách mã hàng/profile mà máy local được phép chọn và chạy.. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `16`. |
| `is_active` | `BOOLEAN` | Có | `true` | `NOT NULL`<br>`DEFAULT true` | Bản ghi còn active và được local sử dụng hay không. | Cần cờ bật/tắt để giữ lịch sử nhưng không cho app sử dụng bản ghi đã ngừng hiệu lực. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `true`. |
| `raw_json` | `JSONB` | Có | `'{}'::jsonb` | `NOT NULL`<br>`DEFAULT '{}'::jsonb` | JSON gốc nhận từ server/API để đối chiếu khi cần debug. | Cần giữ payload gốc để đối chiếu khi mapping field bị sai hoặc server đổi format. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `synced_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm dữ liệu được sync/cache từ server. | Cần mốc sync để biết dữ liệu cache này lấy từ server ở thời điểm nào. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Không có default nên app phải tự set khi nghiệp vụ cần. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App upsert sau config sync; màn chọn mã hàng và logic validate scan đọc bảng này. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

#### `profile_led_code_cache`

Cache tối đa 2 LED code/slot thuộc từng profile để local kiểm LED scan theo slot và suffix.

**Ràng buộc/chỉ mục chính:**

- `CONSTRAINT profile_led_code_cache_slot_between_1_2 CHECK (led_slot BETWEEN 1 AND 2)`
- `CONSTRAINT profile_led_code_cache_profile_slot_unique UNIQUE (profile_id, led_slot)`
- `CONSTRAINT profile_led_code_cache_profile_led_unique UNIQUE (profile_id, led_code_id)`
- `CREATE INDEX IF NOT EXISTS idx_profile_led_code_cache_profile_slot ON profile_led_code_cache (profile_id, led_slot)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `BIGSERIAL` | Có | - | `PK` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `profile_id` | `INTEGER` | Có | - | `NOT NULL`<br>`FK -> profile_cache(profile_id)` | ID profile liên quan. | Cần liên kết dữ liệu với profile/mã hàng đang chạy để validate và thống kê chính xác. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `led_slot` | `INTEGER` | Có | - | `NOT NULL` | Số slot LED trong profile, bắt đầu từ 1. | Cần lưu led slot vì Số slot LED trong profile, bắt đầu từ 1. Field này hỗ trợ giữ cấu hình LED theo từng profile để local validate từng LED scan.. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `led_code_id` | `INTEGER` | Không | - | - | ID LED code trên server, nếu có. | Cần ID tham chiếu led code id để nối dữ liệu giữa các bảng hoặc với server. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `code_full` | `TEXT` | Có | - | `NOT NULL` | Mã đầy đủ của chassis/LED code. | Cần lưu code full vì Mã đầy đủ của chassis/LED code. Field này hỗ trợ giữ cấu hình LED theo từng profile để local validate từng LED scan.. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `code_input` | `TEXT` | Không | - | - | Mã dạng input/ngắn nếu có. | Cần lưu code input vì Mã dạng input/ngắn nếu có. Field này hỗ trợ giữ cấu hình LED theo từng profile để local validate từng LED scan.. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `suffix_check` | `TEXT` | Có | - | `NOT NULL` | Suffix local phải kiểm trong LED scan. | Cần lưu suffix check vì Suffix local phải kiểm trong LED scan. Field này hỗ trợ giữ cấu hình LED theo từng profile để local validate từng LED scan.. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `is_required` | `BOOLEAN` | Có | `true` | `NOT NULL`<br>`DEFAULT true` | Bản ghi/slot này có bắt buộc hay không. | Cần biết slot/code nào bắt buộc để validate thiếu dữ liệu đúng cách. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `true`. |
| `is_active` | `BOOLEAN` | Có | `true` | `NOT NULL`<br>`DEFAULT true` | Bản ghi còn active và được local sử dụng hay không. | Cần cờ bật/tắt để giữ lịch sử nhưng không cho app sử dụng bản ghi đã ngừng hiệu lực. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `true`. |
| `raw_json` | `JSONB` | Có | `'{}'::jsonb` | `NOT NULL`<br>`DEFAULT '{}'::jsonb` | JSON gốc nhận từ server/API để đối chiếu khi cần debug. | Cần giữ payload gốc để đối chiếu khi mapping field bị sai hoặc server đổi format. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `synced_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm dữ liệu được sync/cache từ server. | Cần mốc sync để biết dữ liệu cache này lấy từ server ở thời điểm nào. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Không có default nên app phải tự set khi nghiệp vụ cần. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App upsert cùng profile; validator đọc theo profile_id và led_slot khi kiểm tra LED. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

### Scan, LED và duplicate local

#### `local_scan_records`

Bảng scan chính của máy local. Mỗi lượt scan phải lưu tại đây trước khi gọi server để retry giữ nguyên local_scan_id.

**Ràng buộc/chỉ mục chính:**

- `CREATE INDEX IF NOT EXISTS idx_local_scan_records_scan_at ON local_scan_records (scan_at DESC)`
- `CREATE INDEX IF NOT EXISTS idx_local_scan_records_machine_scan_at ON local_scan_records (machine_code, scan_at DESC)`
- `CREATE INDEX IF NOT EXISTS idx_local_scan_records_profile_duplicate ON local_scan_records (profile_id, duplicate_key, scan_at DESC)`
- `CREATE INDEX IF NOT EXISTS idx_local_scan_records_sync_status ON local_scan_records (sync_status, next_retry_at)`
- `CREATE INDEX IF NOT EXISTS idx_local_scan_records_pending_sync ON local_scan_records (sync_status, scan_at) WHERE sync_status IN ('PENDING', 'FAILED_RETRYABLE')`
- `CREATE INDEX IF NOT EXISTS idx_local_scan_records_final_status ON local_scan_records (final_status, scan_at DESC)`
- `CREATE INDEX IF NOT EXISTS idx_local_scan_records_server_code ON local_scan_records (server_code, scan_at DESC)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `BIGSERIAL` | Có | - | `PK` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `local_scan_id` | `TEXT` | Có | - | `NOT NULL`<br>`UNIQUE` | ID scan duy nhất do local tạo. Retry phải dùng lại đúng ID này. | Cần một ID nghiệp vụ ổn định do local tạo để retry nhiều lần vẫn là cùng một lượt scan. | Sinh một lần trước khi lưu scan; mọi lần submit, sync offline và reconcile phải dùng lại đúng giá trị này. |
| `machine_code` | `TEXT` | Có | - | `NOT NULL` | Mã máy local chính thức sau khi server định danh. | Cần mã nghiệp vụ machine code để đối chiếu với rule/server và hiển thị cho người vận hành. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `profile_id` | `INTEGER` | Không | - | `FK -> profile_cache(profile_id)` | ID profile liên quan. | Cần liên kết dữ liệu với profile/mã hàng đang chạy để validate và thống kê chính xác. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `profile_version` | `INTEGER` | Không | - | - | Version profile local dùng khi scan. | Cần lưu profile version vì Version profile local dùng khi scan. Field này hỗ trợ lưu bản ghi scan chính trước khi gọi server, hỗ trợ retry, duplicate và truy vết.. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `duplicate_key` | `TEXT` | Không | - | - | Khóa duplicate local/server dùng để so trùng, tạo từ before_vendor + vendor_char + after_factory. | Cần lưu duplicate key vì Khóa duplicate local/server dùng để so trùng, tạo từ before_vendor + vendor_char + after_factory. Field này hỗ trợ lưu bản ghi scan chính trước khi gọi server, hỗ trợ retry, duplicate và truy vết.. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `full_code_raw` | `TEXT` | Có | `''` | `NOT NULL`<br>`DEFAULT ''` | Full code thô nhận từ scanner/camera/OCR. | Cần lưu full code raw vì Full code thô nhận từ scanner/camera/OCR. Field này hỗ trợ lưu bản ghi scan chính trước khi gọi server, hỗ trợ retry, duplicate và truy vết.. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `''`. |
| `full_prefix` | `TEXT` | Không | - | - | Đoạn prefix parse được từ full code. | Cần lưu full prefix vì Đoạn prefix parse được từ full code. Field này hỗ trợ lưu bản ghi scan chính trước khi gọi server, hỗ trợ retry, duplicate và truy vết.. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `full_chassis_segment` | `TEXT` | Không | - | - | Đoạn chassis segment parse được từ full code. | Cần lưu full chassis segment vì Đoạn chassis segment parse được từ full code. Field này hỗ trợ lưu bản ghi scan chính trước khi gọi server, hỗ trợ retry, duplicate và truy vết.. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `full_chassis_code` | `TEXT` | Không | - | - | Mã chassis parse được từ full code. | Cần mã nghiệp vụ full chassis code để đối chiếu với rule/server và hiển thị cho người vận hành. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `full_before_vendor` | `TEXT` | Không | - | - | Đoạn ký tự trước vendor trong full code. | Cần lưu full before vendor vì Đoạn ký tự trước vendor trong full code. Field này hỗ trợ lưu bản ghi scan chính trước khi gọi server, hỗ trợ retry, duplicate và truy vết.. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `full_vendor_char` | `TEXT` | Không | - | - | Ký tự vendor parse được từ full code. | Cần lưu full vendor char vì Ký tự vendor parse được từ full code. Field này hỗ trợ lưu bản ghi scan chính trước khi gọi server, hỗ trợ retry, duplicate và truy vết.. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `full_led_code` | `TEXT` | Không | - | - | Đoạn LED code parse được từ full code. | Cần mã nghiệp vụ full led code để đối chiếu với rule/server và hiển thị cho người vận hành. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `full_factory_code` | `TEXT` | Không | - | - | Factory code parse được từ full code. | Cần mã nghiệp vụ full factory code để đối chiếu với rule/server và hiển thị cho người vận hành. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `full_after_factory` | `TEXT` | Không | - | - | Đoạn ký tự sau factory code trong full code. | Cần lưu full after factory vì Đoạn ký tự sau factory code trong full code. Field này hỗ trợ lưu bản ghi scan chính trước khi gọi server, hỗ trợ retry, duplicate và truy vết.. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `chassis_scan_raw` | `TEXT` | Không | - | - | Chuỗi chassis scan thô nếu local có scan riêng. | Cần lưu chassis scan raw vì Chuỗi chassis scan thô nếu local có scan riêng. Field này hỗ trợ lưu bản ghi scan chính trước khi gọi server, hỗ trợ retry, duplicate và truy vết.. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `full_code_json` | `JSONB` | Có | `'{}'::jsonb` | `NOT NULL`<br>`DEFAULT '{}'::jsonb` | JSON cấu trúc full_code sẽ gửi server. | Cần lưu JSON cho full code json vì dữ liệu có cấu trúc nhiều lớp hoặc cần debug nguyên bản. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `led_scans_json` | `JSONB` | Có | `'[]'::jsonb` | `NOT NULL`<br>`DEFAULT '[]'::jsonb` | JSON danh sách led_scans sẽ gửi server. | Cần lưu JSON cho led scans json vì dữ liệu có cấu trúc nhiều lớp hoặc cần debug nguyên bản. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `local_status` | `local_scan_status` | Có | - | `NOT NULL` | Kết quả local tự validate trước khi gọi server: OK hoặc NG. | Cần trạng thái local status để app biết bước xử lý hiện tại và quyết định retry/hiển thị. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `local_ng_reason` | `TEXT` | Không | - | - | Lý do local NG như LED_SUFFIX_NOT_MATCH, LOCAL_DUPLICATE... | Cần lý do local ng reason để biết vì sao một bản ghi bị NG, fail hoặc bị bỏ qua. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Ghi khi có NG/FAILED/SKIPPED; UI/log đọc để giải thích nguyên nhân. |
| `server_code` | `TEXT` | Không | - | - | Mã code server trả, ví dụ SERVER_OK hoặc SERVER_DUPLICATE. | Cần mã nghiệp vụ server code để đối chiếu với rule/server và hiển thị cho người vận hành. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `server_message` | `TEXT` | Không | - | - | Message server trả cho scan/batch. | Cần thông điệp server message để giải thích kết quả cho UI hoặc log. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `server_scan_id` | `INTEGER` | Không | - | - | ID scan record trên server nếu server đã lưu. | Cần ID tham chiếu server scan id để nối dữ liệu giữa các bảng hoặc với server. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `server_first_scan_id` | `INTEGER` | Không | - | - | ID scan đầu tiên server trả khi phát hiện duplicate. | Cần ID tham chiếu server first scan id để nối dữ liệu giữa các bảng hoặc với server. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `server_status` | `server_scan_status` | Có | `'PENDING'` | `NOT NULL`<br>`DEFAULT 'PENDING'` | Status command/scan theo server nếu API trả về. | Cần trạng thái server status để app biết bước xử lý hiện tại và quyết định retry/hiển thị. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `final_status` | `final_scan_status` | Có | `'PENDING_SERVER'` | `NOT NULL`<br>`DEFAULT 'PENDING_SERVER'` | Kết luận cuối cùng local hiển thị: OK, NG, PENDING hoặc PENDING_SERVER. | Cần trạng thái final status để app biết bước xử lý hiện tại và quyết định retry/hiển thị. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `final_ng_reason` | `TEXT` | Không | - | - | Lý do NG cuối cùng sau khi gộp local/server result. | Cần lý do final ng reason để biết vì sao một bản ghi bị NG, fail hoặc bị bỏ qua. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Ghi khi có NG/FAILED/SKIPPED; UI/log đọc để giải thích nguyên nhân. |
| `sync_status` | `local_sync_status` | Có | `'PENDING'` | `NOT NULL`<br>`DEFAULT 'PENDING'` | Trạng thái sync của record này. | Cần trạng thái sync status để app biết bước xử lý hiện tại và quyết định retry/hiển thị. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `sync_attempt_count` | `INTEGER` | Có | `0` | `NOT NULL`<br>`DEFAULT 0` | Số lần local đã thử gửi/sync record này. | Cần lưu sync attempt count vì Số lần local đã thử gửi/sync record này. Field này hỗ trợ lưu bản ghi scan chính trước khi gọi server, hỗ trợ retry, duplicate và truy vết.. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `0`. |
| `last_sync_at` | `TIMESTAMPTZ` | Không | - | - | Lần cuối record được gửi server thành công hoặc có response. | Cần mốc thời gian cho last sync at để truy vết, sắp xếp hoặc tính retry/timeout. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `next_retry_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm local nên retry nếu lỗi tạm thời. | Cần mốc thời gian cho next retry at để truy vết, sắp xếp hoặc tính retry/timeout. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `last_error_code` | `TEXT` | Không | - | - | Mã lỗi cuối cùng khi gửi/sync record. | Cần mã nghiệp vụ last error code để đối chiếu với rule/server và hiển thị cho người vận hành. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Ghi đè bằng giá trị mới nhất; dùng để hiển thị tình trạng hiện tại. |
| `last_error_message` | `TEXT` | Không | - | - | Message lỗi cuối cùng khi gửi/sync record. | Cần thông điệp last error message để giải thích kết quả cho UI hoặc log. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Ghi đè bằng giá trị mới nhất; dùng để hiển thị tình trạng hiện tại. |
| `scan_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm scan gốc trên máy local. | Cần mốc thời gian cho scan at để truy vết, sắp xếp hoặc tính retry/timeout. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App insert ngay khi có scan, sau đó update theo kết quả local/server/reconcile. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

#### `local_scan_led_items`

Chi tiết từng LED item trong một scan local, dùng truy vết lỗi LED và tạo manifest khi reconcile.

**Ràng buộc/chỉ mục chính:**

- `CONSTRAINT local_scan_led_items_slot_positive CHECK (led_slot > 0)`
- `CONSTRAINT local_scan_led_items_index_positive CHECK (led_index > 0)`
- `CONSTRAINT local_scan_led_items_unique_item UNIQUE (scan_id, led_slot, led_index)`
- `CREATE INDEX IF NOT EXISTS idx_local_scan_led_items_local_scan_id ON local_scan_led_items (local_scan_id)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `BIGSERIAL` | Có | - | `PK` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `scan_id` | `BIGINT` | Có | - | `NOT NULL`<br>`FK -> local_scan_records(id)` | FK tới local_scan_records.id. | Cần ID tham chiếu scan id để nối dữ liệu giữa các bảng hoặc với server. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `local_scan_id` | `TEXT` | Có | - | `NOT NULL`<br>`FK -> local_scan_records(local_scan_id)` | ID scan duy nhất do local tạo. Retry phải dùng lại đúng ID này. | Cần giữ ID scan nghiệp vụ của bản ghi cha để gửi payload và debug theo đúng lượt scan. | Ghi cùng lúc tạo LED item; dùng khi build led_scans_json hoặc lọc toàn bộ LED của một scan. |
| `led_slot` | `INTEGER` | Có | - | `NOT NULL` | Số slot LED trong profile, bắt đầu từ 1. | Cần lưu led slot vì Số slot LED trong profile, bắt đầu từ 1. Field này hỗ trợ lưu chi tiết từng LED scan thuộc một lượt scan chính.. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `led_index` | `INTEGER` | Có | - | `NOT NULL` | Thứ tự LED item trong slot nếu có nhiều item. | Cần lưu led index vì Thứ tự LED item trong slot nếu có nhiều item. Field này hỗ trợ lưu chi tiết từng LED scan thuộc một lượt scan chính.. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `led_scan_raw` | `TEXT` | Có | - | `NOT NULL` | Chuỗi LED scan thô. | Cần lưu led scan raw vì Chuỗi LED scan thô. Field này hỗ trợ lưu chi tiết từng LED scan thuộc một lượt scan chính.. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `led_lot_no` | `TEXT` | Không | - | - | Lot number parse được từ LED scan. | Cần lưu led lot no vì Lot number parse được từ LED scan. Field này hỗ trợ lưu chi tiết từng LED scan thuộc một lượt scan chính.. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `vendor_char` | `TEXT` | Không | - | - | Ký tự vendor hợp lệ trong full code và LED scan. | Cần lưu vendor char vì Ký tự vendor hợp lệ trong full code và LED scan. Field này hỗ trợ lưu chi tiết từng LED scan thuộc một lượt scan chính.. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `led_suffix` | `TEXT` | Không | - | - | Suffix parse được để so với suffix_check. | Cần lưu led suffix vì Suffix parse được để so với suffix_check. Field này hỗ trợ lưu chi tiết từng LED scan thuộc một lượt scan chính.. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `local_status` | `local_scan_status` | Có | - | `NOT NULL` | Kết quả validate riêng cho LED item này: OK hoặc NG. | Cần trạng thái local status để app biết bước xử lý hiện tại và quyết định retry/hiển thị. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `ng_reason` | `TEXT` | Không | - | - | Lý do nghiệp vụ liên quan tới trạng thái NG, fail hoặc bị bỏ qua. | Cần lý do ng reason để biết vì sao một bản ghi bị NG, fail hoặc bị bỏ qua. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. Ghi khi có NG/FAILED/SKIPPED; UI/log đọc để giải thích nguyên nhân. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App insert theo từng LED item sau khi parse; update khi validate lại hoặc sync lại. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

#### `local_duplicate_keys`

Duplicate cục bộ của máy local theo profile và scope, chỉ dùng cảnh báo local, không thay duplicate nhiều ngày của server.

**Ràng buộc/chỉ mục chính:**

- `CONSTRAINT local_duplicate_keys_unique_key UNIQUE (profile_id, duplicate_key, scope_key)`
- `CREATE INDEX IF NOT EXISTS idx_local_duplicate_keys_lookup ON local_duplicate_keys (profile_id, duplicate_key, scope_key, status)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `BIGSERIAL` | Có | - | `PK` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | App tra cứu trước khi nhận scan mới và insert khi scan được chấp nhận trong scope duplicate. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `profile_id` | `INTEGER` | Có | - | `NOT NULL`<br>`FK -> profile_cache(profile_id)` | ID profile liên quan. | Cần liên kết dữ liệu với profile/mã hàng đang chạy để validate và thống kê chính xác. | App tra cứu trước khi nhận scan mới và insert khi scan được chấp nhận trong scope duplicate. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `duplicate_key` | `TEXT` | Có | - | `NOT NULL` | Khóa duplicate local/server dùng để so trùng, tạo từ before_vendor + vendor_char + after_factory. | Cần khóa duplicate đã chuẩn hóa để tra cứu nhanh thay vì so toàn bộ chuỗi scan thô. | Tạo từ rule duplicate hiện hành; lookup trước khi accept scan và insert sau khi scan hợp lệ. |
| `scope_key` | `TEXT` | Có | - | `NOT NULL` | Khóa scope local, ví dụ ngày hoặc máy-ngày tùy duplicate_scope. | Cần lưu scope key vì Khóa scope local, ví dụ ngày hoặc máy-ngày tùy duplicate_scope. Field này hỗ trợ chặn trùng cục bộ nhanh trước khi gửi dữ liệu lên server.. | App tra cứu trước khi nhận scan mới và insert khi scan được chấp nhận trong scope duplicate. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `first_local_scan_id` | `TEXT` | Không | - | `FK -> local_scan_records(local_scan_id)` | Scan local đầu tiên tạo ra duplicate key này. | Cần ID tham chiếu first local scan id để nối dữ liệu giữa các bảng hoặc với server. | App tra cứu trước khi nhận scan mới và insert khi scan được chấp nhận trong scope duplicate. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `first_scan_at` | `TIMESTAMPTZ` | Có | - | `NOT NULL` | Thời điểm scan đầu tiên trong scope local. | Cần mốc thời gian cho first scan at để truy vết, sắp xếp hoặc tính retry/timeout. | App tra cứu trước khi nhận scan mới và insert khi scan được chấp nhận trong scope duplicate. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `machine_code` | `TEXT` | Không | - | - | Mã máy local chính thức sau khi server định danh. | Cần mã nghiệp vụ machine code để đối chiếu với rule/server và hiển thị cho người vận hành. | App tra cứu trước khi nhận scan mới và insert khi scan được chấp nhận trong scope duplicate. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `status` | `TEXT` | Có | `'ACTIVE'` | `NOT NULL`<br>`CHECK`<br>`DEFAULT 'ACTIVE'` | Trạng thái hiện tại của bản ghi. | Cần trạng thái tổng quát để lọc bản ghi active/inactive hoặc đang xử lý. | App tra cứu trước khi nhận scan mới và insert khi scan được chấp nhận trong scope duplicate. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App tra cứu trước khi nhận scan mới và insert khi scan được chấp nhận trong scope duplicate. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App tra cứu trước khi nhận scan mới và insert khi scan được chấp nhận trong scope duplicate. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

### Sync offline và reconcile

#### `sync_batches`

Header batch sync khi local gửi các scan pending/offline lên server.

**Ràng buộc/chỉ mục chính:**

- `CREATE INDEX IF NOT EXISTS idx_sync_batches_status ON sync_batches (status, created_at DESC)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `BIGSERIAL` | Có | - | `PK` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `batch_code` | `TEXT` | Có | - | `NOT NULL`<br>`UNIQUE` | Mã nghiệp vụ liên quan. | Cần mã nghiệp vụ batch code để đối chiếu với rule/server và hiển thị cho người vận hành. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `trigger_type` | `sync_batch_trigger_type` | Có | - | `NOT NULL` | Lý do tạo batch: STARTUP, SHUTDOWN, NETWORK_RESTORED hoặc MANUAL. | Cần lưu trigger type vì Lý do tạo batch: STARTUP, SHUTDOWN, NETWORK_RESTORED hoặc MANUAL. Field này hỗ trợ gom các scan cần đồng bộ offline thành từng batch có thể retry.. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `total_sent` | `INTEGER` | Có | `0` | `NOT NULL`<br>`DEFAULT 0` | Số scan local gửi trong batch. | Cần số tổng total sent để tổng kết batch/phiên và đối chiếu số lượng. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Cập nhật sau khi xử lý xong nhóm dữ liệu; dùng cho dashboard/tổng kết. |
| `total_ok` | `INTEGER` | Có | `0` | `NOT NULL`<br>`DEFAULT 0` | Số scan trong batch được server chốt OK. | Cần số tổng total ok để tổng kết batch/phiên và đối chiếu số lượng. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Cập nhật sau khi xử lý xong nhóm dữ liệu; dùng cho dashboard/tổng kết. |
| `total_ng` | `INTEGER` | Có | `0` | `NOT NULL`<br>`DEFAULT 0` | Số scan trong batch được chốt NG. | Cần số tổng total ng để tổng kết batch/phiên và đối chiếu số lượng. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Cập nhật sau khi xử lý xong nhóm dữ liệu; dùng cho dashboard/tổng kết. |
| `total_failed` | `INTEGER` | Có | `0` | `NOT NULL`<br>`DEFAULT 0` | Số scan gửi lỗi hoặc không được xử lý. | Cần số tổng total failed để tổng kết batch/phiên và đối chiếu số lượng. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Cập nhật sau khi xử lý xong nhóm dữ liệu; dùng cho dashboard/tổng kết. |
| `server_batch_id` | `INTEGER` | Không | - | - | ID batch trên server nếu API trả về. | Cần ID tham chiếu server batch id để nối dữ liệu giữa các bảng hoặc với server. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `server_code` | `TEXT` | Không | - | - | Mã code server trả, ví dụ SERVER_OK hoặc SERVER_DUPLICATE. | Cần mã nghiệp vụ server code để đối chiếu với rule/server và hiển thị cho người vận hành. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `server_message` | `TEXT` | Không | - | - | Message server trả cho scan/batch. | Cần thông điệp server message để giải thích kết quả cho UI hoặc log. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `status` | `sync_batch_status` | Có | `'PENDING'` | `NOT NULL`<br>`DEFAULT 'PENDING'` | Trạng thái hiện tại của bản ghi. | Cần trạng thái tổng quát để lọc bản ghi active/inactive hoặc đang xử lý. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `summary_json` | `JSONB` | Có | `'{}'::jsonb` | `NOT NULL`<br>`DEFAULT '{}'::jsonb` | Tổng hợp batch gửi server hoặc kết quả xử lý. | Cần lưu JSON cho summary json vì dữ liệu có cấu trúc nhiều lớp hoặc cần debug nguyên bản. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `request_json` | `JSONB` | Có | `'{}'::jsonb` | `NOT NULL`<br>`DEFAULT '{}'::jsonb` | Payload request đã gửi. | Cần lưu request đã gửi để tái hiện lỗi API và kiểm tra local đã gửi dữ liệu gì. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `response_json` | `JSONB` | Không | - | - | Response JSON đã nhận. | Cần lưu response gốc để debug kết quả server trả về. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `error_message` | `TEXT` | Không | - | - | Thông điệp lỗi nếu thao tác thất bại. | Cần lưu lỗi dạng người đọc hiểu được để operator/dev biết nguyên nhân thất bại. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `started_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm bắt đầu xử lý/gửi. | Cần mốc thời gian cho started at để truy vết, sắp xếp hoặc tính retry/timeout. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `finished_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm hoàn tất xử lý/gửi. | Cần mốc thời gian cho finished at để truy vết, sắp xếp hoặc tính retry/timeout. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App tạo khi sync offline/manual/startup; update tổng kết sau khi server phản hồi. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

#### `sync_batch_items`

Kết quả từng scan nằm trong batch sync để biết record nào OK, NG, fail hoặc cần retry.

**Ràng buộc/chỉ mục chính:**

- `CONSTRAINT sync_batch_items_unique_scan UNIQUE (batch_id, local_scan_id)`
- `CREATE INDEX IF NOT EXISTS idx_sync_batch_items_scan ON sync_batch_items (local_scan_id)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `BIGSERIAL` | Có | - | `PK` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `batch_id` | `BIGINT` | Có | - | `NOT NULL`<br>`FK -> sync_batches(id)` | FK tới sync_batches.id. | Cần ID tham chiếu batch id để nối dữ liệu giữa các bảng hoặc với server. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `local_scan_id` | `TEXT` | Có | - | `NOT NULL`<br>`FK -> local_scan_records(local_scan_id)` | ID scan duy nhất do local tạo. Retry phải dùng lại đúng ID này. | Cần biết item trong batch đang đồng bộ cho scan nào để update đúng record sau response server. | Ghi khi tạo batch item; dùng để cập nhật sync_status/final_status cho scan sau khi batch kết thúc. |
| `result_success` | `BOOLEAN` | Có | `false` | `NOT NULL`<br>`DEFAULT false` | Record này có sync thành công trong batch hay không. | Cần lưu result success vì Record này có sync thành công trong batch hay không. Field này hỗ trợ ghi kết quả sync của từng scan trong một batch.. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `false`. |
| `result_code` | `TEXT` | Không | - | - | Code nghiệp vụ server trả. | Cần mã nghiệp vụ result code để đối chiếu với rule/server và hiển thị cho người vận hành. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `result_message` | `TEXT` | Không | - | - | Message server hoặc local cho record trong batch. | Cần thông điệp result message để giải thích kết quả cho UI hoặc log. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `server_scan_id` | `INTEGER` | Không | - | - | ID scan record trên server nếu server đã lưu. | Cần ID tham chiếu server scan id để nối dữ liệu giữa các bảng hoặc với server. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `final_status` | `final_scan_status` | Không | - | - | Kết luận cuối cùng local hiển thị: OK, NG, PENDING hoặc PENDING_SERVER. | Cần trạng thái final status để app biết bước xử lý hiện tại và quyết định retry/hiển thị. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `ng_reason` | `TEXT` | Không | - | - | Lý do nghiệp vụ liên quan tới trạng thái NG, fail hoặc bị bỏ qua. | Cần lý do ng reason để biết vì sao một bản ghi bị NG, fail hoặc bị bỏ qua. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. Ghi khi có NG/FAILED/SKIPPED; UI/log đọc để giải thích nguyên nhân. |
| `response_json` | `JSONB` | Không | - | - | Response JSON đã nhận. | Cần lưu response gốc để debug kết quả server trả về. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `error_message` | `TEXT` | Không | - | - | Thông điệp lỗi nếu thao tác thất bại. | Cần lưu lỗi dạng người đọc hiểu được để operator/dev biết nguyên nhân thất bại. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App tạo theo từng record trong batch; update result sau khi xử lý từng scan. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

### Command, thông báo và log

#### `command_inbox`

Inbox command server gửi qua polling. Local lưu command, xử lý rồi ack/fail lại server.

**Ràng buộc/chỉ mục chính:**

- `CREATE INDEX IF NOT EXISTS idx_command_inbox_status ON command_inbox (local_status, received_at DESC)`
- `CREATE INDEX IF NOT EXISTS idx_command_inbox_type ON command_inbox (command_type, local_status)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `BIGSERIAL` | Có | - | `PK` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `server_command_id` | `INTEGER` | Có | - | `NOT NULL`<br>`UNIQUE` | ID command trên server. | Cần ID tham chiếu server command id để nối dữ liệu giữa các bảng hoặc với server. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `machine_code` | `TEXT` | Có | - | `NOT NULL` | Mã máy local chính thức sau khi server định danh. | Cần mã nghiệp vụ machine code để đối chiếu với rule/server và hiển thị cho người vận hành. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `command_type` | `machine_command_type` | Có | - | `NOT NULL` | Loại command cần xử lý. | Cần lưu command type vì Loại command cần xử lý. Field này hỗ trợ lưu lệnh server gửi xuống để local xử lý và ACK lại.. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `payload_json` | `JSONB` | Có | `'{}'::jsonb` | `NOT NULL`<br>`DEFAULT '{}'::jsonb` | Payload JSON liên quan tới event, command hoặc thông báo. | Cần giữ payload chi tiết của sự kiện/lệnh/thông báo mà các cột riêng không thể chứa hết. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `server_status` | `TEXT` | Không | - | - | Status command/scan theo server nếu API trả về. | Cần trạng thái server status để app biết bước xử lý hiện tại và quyết định retry/hiển thị. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `local_status` | `command_local_status` | Có | `'PENDING'` | `NOT NULL`<br>`DEFAULT 'PENDING'` | Trạng thái local xử lý command: PENDING, RUNNING, ACKED, FAILED hoặc SKIPPED. | Cần trạng thái local status để app biết bước xử lý hiện tại và quyết định retry/hiển thị. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `received_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm local nhận command. | Cần mốc thời gian cho received at để truy vết, sắp xếp hoặc tính retry/timeout. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `started_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm bắt đầu xử lý/gửi. | Cần mốc thời gian cho started at để truy vết, sắp xếp hoặc tính retry/timeout. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `finished_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm hoàn tất xử lý/gửi. | Cần mốc thời gian cho finished at để truy vết, sắp xếp hoặc tính retry/timeout. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `ack_sent_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm local gửi ACK/FAILED về server. | Cần mốc thời gian cho ack sent at để truy vết, sắp xếp hoặc tính retry/timeout. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `ack_status` | `command_ack_status` | Không | - | - | ACK hoặc FAILED gửi về server. | Cần trạng thái ack status để app biết bước xử lý hiện tại và quyết định retry/hiển thị. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `error_message` | `TEXT` | Không | - | - | Thông điệp lỗi nếu thao tác thất bại. | Cần lưu lỗi dạng người đọc hiểu được để operator/dev biết nguyên nhân thất bại. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `raw_json` | `JSONB` | Có | `'{}'::jsonb` | `NOT NULL`<br>`DEFAULT '{}'::jsonb` | JSON gốc nhận từ server/API để đối chiếu khi cần debug. | Cần giữ payload gốc để đối chiếu khi mapping field bị sai hoặc server đổi format. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App lưu command khi poll được, update trạng thái xử lý rồi gửi ACK/FAILED lên server. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

#### `local_notifications`

Thông báo nội bộ cho UI Python local, khác với notification_events của server UI.

**Ràng buộc/chỉ mục chính:**

- `CREATE INDEX IF NOT EXISTS idx_local_notifications_status ON local_notifications (status, created_at DESC)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `BIGSERIAL` | Có | - | `PK` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `noti_code` | `TEXT` | Có | - | `NOT NULL` | Mã loại thông báo local. | Cần mã nghiệp vụ noti code để đối chiếu với rule/server và hiển thị cho người vận hành. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `severity` | `local_notification_severity` | Có | - | `NOT NULL` | Mức độ INFO, WARNING, ERROR hoặc CRITICAL. | Cần lưu severity vì Mức độ INFO, WARNING, ERROR hoặc CRITICAL. Field này hỗ trợ lưu thông báo nội bộ để app Python local hiển thị và truy vết.. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `title` | `TEXT` | Có | - | `NOT NULL` | Tiêu đề ngắn hiển thị trên UI local. | Cần lưu title vì Tiêu đề ngắn hiển thị trên UI local. Field này hỗ trợ lưu thông báo nội bộ để app Python local hiển thị và truy vết.. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `message` | `TEXT` | Có | - | `NOT NULL` | Nội dung chi tiết của thông báo hiển thị trên UI local. | Cần lưu message vì Nội dung chi tiết của thông báo hiển thị trên UI local. Field này hỗ trợ lưu thông báo nội bộ để app Python local hiển thị và truy vết.. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `status` | `local_notification_status` | Có | `'NEW'` | `NOT NULL`<br>`DEFAULT 'NEW'` | Trạng thái hiện tại của bản ghi. | Cần trạng thái tổng quát để lọc bản ghi active/inactive hoặc đang xử lý. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Update mỗi khi trạng thái thay đổi; UI và worker lọc theo field này để xử lý tiếp. |
| `source` | `local_notification_source` | Có | `'LOCAL'` | `NOT NULL`<br>`DEFAULT 'LOCAL'` | Nguồn thông báo: LOCAL, SERVER_COMMAND hoặc SERVER_RESPONSE. | Cần lưu source vì Nguồn thông báo: LOCAL, SERVER_COMMAND hoặc SERVER_RESPONSE. Field này hỗ trợ lưu thông báo nội bộ để app Python local hiển thị và truy vết.. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `'LOCAL'`. |
| `related_local_scan_id` | `TEXT` | Không | - | `FK -> local_scan_records(local_scan_id)` | Scan local liên quan nếu có. | Cần ID tham chiếu related local scan id để nối dữ liệu giữa các bảng hoặc với server. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `related_batch_code` | `TEXT` | Không | - | `FK -> sync_batches(batch_code)` | Batch sync liên quan nếu có. | Cần mã nghiệp vụ related batch code để đối chiếu với rule/server và hiển thị cho người vận hành. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `related_server_command_id` | `INTEGER` | Không | - | `FK -> command_inbox(server_command_id)` | Command server liên quan nếu có. | Cần ID tham chiếu related server command id để nối dữ liệu giữa các bảng hoặc với server. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `payload_json` | `JSONB` | Có | `'{}'::jsonb` | `NOT NULL`<br>`DEFAULT '{}'::jsonb` | Payload JSON liên quan tới event, command hoặc thông báo. | Cần giữ payload chi tiết của sự kiện/lệnh/thông báo mà các cột riêng không thể chứa hết. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `updated_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm cập nhật bản ghi gần nhất. | Cần mốc cập nhật để biết bản ghi đã thay đổi lần cuối khi nào. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
| `read_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm người dùng đọc thông báo. | Cần mốc thời gian cho read at để truy vết, sắp xếp hoặc tính retry/timeout. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |
| `dismissed_at` | `TIMESTAMPTZ` | Không | - | - | Thời điểm người dùng ẩn thông báo. | Cần mốc thời gian cho dismissed at để truy vết, sắp xếp hoặc tính retry/timeout. | App insert khi có cảnh báo/lỗi/sự kiện; UI đọc và update read_at/dismissed_at. Ghi đúng thời điểm sự kiện xảy ra; dùng để sort, retry, timeout hoặc báo cáo. |

#### `api_request_logs`

Log request/response khi local gọi API server, phục vụ debug máy local đã gửi gì và server trả gì.

**Ràng buộc/chỉ mục chính:**

- `CREATE INDEX IF NOT EXISTS idx_api_request_logs_type_time ON api_request_logs (request_type, created_at DESC)`
- `CREATE INDEX IF NOT EXISTS idx_api_request_logs_scan ON api_request_logs (local_scan_id)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `BIGSERIAL` | Có | - | `PK` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `request_type` | `TEXT` | Có | - | `NOT NULL` | Tên nghiệp vụ request, ví dụ SUBMIT_SCAN, HEARTBEAT, RECONCILE_CHECK. | Cần lưu request type vì Tên nghiệp vụ request, ví dụ SUBMIT_SCAN, HEARTBEAT, RECONCILE_CHECK. Field này hỗ trợ ghi log mọi request local gọi lên server để debug kết nối/API.. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `method` | `api_request_method` | Có | - | `NOT NULL` | HTTP method request. | Cần lưu method vì HTTP method request. Field này hỗ trợ ghi log mọi request local gọi lên server để debug kết nối/API.. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `url` | `TEXT` | Có | - | `NOT NULL` | URL server mà local gọi. | Cần lưu url vì URL server mà local gọi. Field này hỗ trợ ghi log mọi request local gọi lên server để debug kết nối/API.. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `local_scan_id` | `TEXT` | Không | - | `FK -> local_scan_records(local_scan_id)` | ID scan duy nhất do local tạo. Retry phải dùng lại đúng ID này. | Cần liên kết log request với lượt scan cụ thể để debug lỗi submit/retry. | Ghi khi request liên quan tới scan; để trống nếu request là health/config/heartbeat. |
| `batch_code` | `TEXT` | Không | - | `FK -> sync_batches(batch_code)` | Mã nghiệp vụ liên quan. | Cần mã nghiệp vụ batch code để đối chiếu với rule/server và hiển thị cho người vận hành. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `command_inbox_id` | `BIGINT` | Không | - | `FK -> command_inbox(id)` | Command inbox liên quan nếu request là ACK command. | Cần ID tham chiếu command inbox id để nối dữ liệu giữa các bảng hoặc với server. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `request_json` | `JSONB` | Không | - | - | Payload request đã gửi. | Cần lưu request đã gửi để tái hiện lỗi API và kiểm tra local đã gửi dữ liệu gì. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `response_status_code` | `INTEGER` | Không | - | - | HTTP status code server trả. | Cần mã nghiệp vụ response status code để đối chiếu với rule/server và hiển thị cho người vận hành. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `response_json` | `JSONB` | Không | - | - | Response JSON đã nhận. | Cần lưu response gốc để debug kết quả server trả về. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `result_code` | `TEXT` | Không | - | - | Code nghiệp vụ server trả. | Cần mã nghiệp vụ result code để đối chiếu với rule/server và hiển thị cho người vận hành. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `success` | `BOOLEAN` | Có | `false` | `NOT NULL`<br>`DEFAULT false` | Request có được coi là thành công hay không. | Cần lưu success vì Request có được coi là thành công hay không. Field này hỗ trợ ghi log mọi request local gọi lên server để debug kết nối/API.. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `false`. |
| `error_message` | `TEXT` | Không | - | - | Thông điệp lỗi nếu thao tác thất bại. | Cần lưu lỗi dạng người đọc hiểu được để operator/dev biết nguyên nhân thất bại. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `duration_ms` | `INTEGER` | Không | - | - | Thời gian request tính bằng millisecond. | Cần lưu duration ms vì Thời gian request tính bằng millisecond. Field này hỗ trợ ghi log mọi request local gọi lên server để debug kết nối/API.. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Có thể để trống khi dữ liệu chưa có hoặc không áp dụng. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | HTTP client ghi sau mỗi lần gọi server; dùng để xem lại request/response và thời gian phản hồi. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |

#### `app_event_logs`

Log sự kiện runtime nội bộ của app local như boot, parse lỗi, DB lỗi, reconnect hoặc worker crash.

**Ràng buộc/chỉ mục chính:**

- `CREATE INDEX IF NOT EXISTS idx_app_event_logs_code_time ON app_event_logs (event_code, created_at DESC)`

| Field | Kiểu | Bắt buộc | Default | Ràng buộc | Ý nghĩa | Vì sao có | Cách dùng trong app local |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | `BIGSERIAL` | Có | - | `PK` | Khóa chính nội bộ của bảng. | Cần khóa chính nội bộ để app local tham chiếu, update và liên kết dữ liệu trong DB local. | App ghi append-only khi có lỗi hoặc mốc vận hành quan trọng; dùng cho debug nội bộ. DB tự cấp/giữ khóa này; app dùng để join/update nội bộ, không dùng thay cho ID nghiệp vụ gửi server. |
| `level` | `app_event_level` | Có | `'INFO'` | `NOT NULL`<br>`DEFAULT 'INFO'` | Mức log nội bộ. | Cần lưu level vì Mức log nội bộ. Field này hỗ trợ ghi log sự kiện nội bộ của app local để điều tra lỗi vận hành.. | App ghi append-only khi có lỗi hoặc mốc vận hành quan trọng; dùng cho debug nội bộ. Bắt buộc có khi tạo bản ghi. Nếu không truyền, PostgreSQL dùng default `'INFO'`. |
| `event_code` | `TEXT` | Có | - | `NOT NULL` | Mã sự kiện nội bộ. | Cần mã nghiệp vụ event code để đối chiếu với rule/server và hiển thị cho người vận hành. | App ghi append-only khi có lỗi hoặc mốc vận hành quan trọng; dùng cho debug nội bộ. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `message` | `TEXT` | Có | - | `NOT NULL` | Nội dung log nội bộ của app local. | Cần lưu message vì Nội dung log nội bộ của app local. Field này hỗ trợ ghi log sự kiện nội bộ của app local để điều tra lỗi vận hành.. | App ghi append-only khi có lỗi hoặc mốc vận hành quan trọng; dùng cho debug nội bộ. Bắt buộc có khi tạo bản ghi. Không có default nên app phải tự set khi nghiệp vụ cần. |
| `payload_json` | `JSONB` | Không | - | - | Payload JSON liên quan tới event, command hoặc thông báo. | Cần giữ payload chi tiết của sự kiện/lệnh/thông báo mà các cột riêng không thể chứa hết. | App ghi append-only khi có lỗi hoặc mốc vận hành quan trọng; dùng cho debug nội bộ. Ghi JSON đầy đủ khi có request/response/payload; đọc lại khi cần retry, debug hoặc dựng lại payload. |
| `created_at` | `TIMESTAMPTZ` | Có | `now()` | `NOT NULL`<br>`DEFAULT now()` | Thời điểm tạo bản ghi. | Cần mốc tạo để truy vết bản ghi được sinh ra khi nào và sắp xếp lịch sử. | App ghi append-only khi có lỗi hoặc mốc vận hành quan trọng; dùng cho debug nội bộ. Nếu không truyền, PostgreSQL dùng default `now()`. UI/log dùng để sắp xếp và kiểm tra độ mới dữ liệu. |
<!-- LOCAL_DB_FIELD_GUIDE_END -->

## 5. Query kiểm tra sau khi chạy

Chạy các query này trong database `samsung_qr_local`.

```sql
SET search_path TO local_qr, public;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'local_qr'
ORDER BY table_name;
```

Kỳ vọng có các bảng chính:

```txt
api_request_logs
app_event_logs
command_inbox
id_counters
local_app_settings
local_duplicate_keys
local_notifications
local_scan_led_items
local_scan_records
machine_cache
profile_cache
profile_led_code_cache
schema_migrations
server_settings_cache
sync_batch_items
sync_batches
```

Kiểm tra seed mặc định:

```sql
SET search_path TO local_qr, public;

SELECT * FROM local_app_settings;
SELECT * FROM server_settings_cache;
SELECT * FROM schema_migrations;
```

Kiểm tra view:

```sql
SET search_path TO local_qr, public;

SELECT * FROM v_pending_sync_scans;
SELECT * FROM v_active_profiles;
SELECT * FROM v_today_scan_summary;
SELECT * FROM v_latest_notifications;
```

## 6. Connection string Python

Nếu dùng schema `local_qr`, app Python cần set `search_path`.

Ví dụ DSN:

```txt
postgresql://samsung_qr_local_user:ChangeMe_Use_Strong_Local_Password@127.0.0.1:5432/samsung_qr_local?options=-csearch_path%3Dlocal_qr%2Cpublic
```

Ví dụ với `psycopg`:

```python
import psycopg

conn = psycopg.connect(
    host="127.0.0.1",
    port=5432,
    dbname="samsung_qr_local",
    user="samsung_qr_local_user",
    password="ChangeMe_Use_Strong_Local_Password",
    options="-c search_path=local_qr,public",
)
```

## 7. Cách tạo `local_scan_id`

Tạo ID trong transaction để tránh trùng khi app có nhiều thread.

```sql
SET search_path TO local_qr, public;

WITH next_counter AS (
  INSERT INTO id_counters (counter_name, counter_date, current_value)
  VALUES ('local_scan_sequence', CURRENT_DATE, 1)
  ON CONFLICT (counter_name, counter_date)
  DO UPDATE SET current_value = id_counters.current_value + 1
  RETURNING counter_date, current_value
)
SELECT
  'LS-' ||
  COALESCE((SELECT machine_code FROM local_app_settings WHERE id = 1), 'LOCAL') ||
  '-' ||
  to_char(counter_date, 'YYYYMMDD') ||
  '-' ||
  lpad(current_value::text, 6, '0') AS local_scan_id
FROM next_counter;
```

Ví dụ kết quả:

```txt
LS-LOCAL01-20260713-000001
```

## 8. Cách tạo `batch_code`

```sql
SET search_path TO local_qr, public;

WITH next_counter AS (
  INSERT INTO id_counters (counter_name, counter_date, current_value)
  VALUES ('batch_sequence', CURRENT_DATE, 1)
  ON CONFLICT (counter_name, counter_date)
  DO UPDATE SET current_value = id_counters.current_value + 1
  RETURNING counter_date, current_value
)
SELECT
  'BATCH-' ||
  COALESCE((SELECT machine_code FROM local_app_settings WHERE id = 1), 'LOCAL') ||
  '-' ||
  to_char(counter_date, 'YYYYMMDD') ||
  '-' ||
  lpad(current_value::text, 4, '0') AS batch_code
FROM next_counter;
```

Ví dụ kết quả:

```txt
BATCH-LOCAL01-20260713-0001
```

## 9. Mapping bảng với luồng API

### Health và heartbeat

API liên quan:

```txt
GET  /api/health
POST /api/machines/heartbeat
```

Bảng local nên ghi:

- `local_app_settings.server_online`
- `local_app_settings.local_runtime_status`
- `local_app_settings.local_status_message`
- `local_app_settings.local_status_updated_at`
- `local_app_settings.last_health_at`
- `local_app_settings.last_heartbeat_at`
- `local_app_settings.last_server_error_code`
- `local_app_settings.last_server_error_message`
- `api_request_logs`
- `local_notifications` nếu trạng thái online/offline thay đổi

### Pairing máy local mới

API liên quan:

```txt
GET  /api/machines/identity/status?serial=...&uid=...
POST /api/machines/register-request
GET  /api/machines/register-requests/{request_id}/status?serial=...&uid=...
```

Khi gọi `POST /api/machines/register-request`, request body chỉ cần 3 field: `serial`, `uid`, `ip_address`. Server tự tạo raw key theo format:

```txt
{machine_serial}|{machine_uid}
```

Bảng local nên ghi:

- `local_app_settings.machine_serial`
- `local_app_settings.machine_uid`
- `local_app_settings.machine_license_key` nếu local muốn tự lưu license raw để đối chiếu
- `local_app_settings.registration_request_id`
- `local_app_settings.registration_status`
- `local_app_settings.license_activated_at` nếu API status trả timestamp license đã được server import/kích hoạt
- `local_app_settings.local_runtime_status`: `NOT_REGISTERED`, `REGISTERING`, `WAITING_LICENSE`, `WAITING_APPROVAL`, `REJECTED` hoặc `READY`
- `local_app_settings.machine_code` sau khi server trả `MACHINE_REGISTER_APPROVED`
- `api_request_logs`
- `local_notifications` nếu bị trùng hoặc bị reject

### Reload config

API liên quan:

```txt
GET /api/machines/config?serial=...&uid=...
```

Bảng local nên ghi:

- `server_settings_cache`
- `machine_cache`
- `profile_cache`
- `vendor_cache`
- `profile_led_code_cache`
- `local_app_settings.last_config_sync_at`
- `local_app_settings.local_runtime_status = 'READY'` nếu config hợp lệ và có profile active
- `api_request_logs`

Khi reload profile, nên dùng transaction:

1. Upsert `server_settings_cache`.
2. Upsert `machine_cache`.
3. Upsert từng dòng `vendor_cache`.
4. Upsert từng dòng `profile_cache`.
5. Xóa hoặc inactive LED cache cũ của profile.
6. Upsert từng dòng `profile_led_code_cache`.
7. Update `local_app_settings.active_profile_id`.

### Submit scan online

API liên quan:

```txt
POST /api/scans/submit
```

Bảng local nên ghi trước khi gọi API:

- `local_scan_records`
- `local_scan_led_items`

Bảng local nên update sau khi có response:

- `local_scan_records.server_code`
- `local_scan_records.server_message`
- `local_scan_records.server_scan_id`
- `local_scan_records.server_status`
- `local_scan_records.final_status`
- `local_scan_records.final_ng_reason`
- `local_scan_records.sync_status`
- `api_request_logs`
- `local_notifications` nếu response là NG, duplicate hoặc lỗi

### Sync offline batch

API liên quan:

```txt
POST /api/sync/batches/submit
```

Bảng local nên ghi:

- `sync_batches`
- `sync_batch_items`
- `local_scan_records.sync_status`
- `local_scan_records.sync_attempt_count`
- `local_app_settings.local_runtime_status = 'SYNCING'` trong lúc gửi batch, sau đó trả về `READY` nếu không có lỗi chặn vận hành
- `local_notifications`
- `api_request_logs`

### Đối soát dữ liệu local/server

API liên quan:

```txt
POST /api/sync/reconcile/check
POST /api/sync/reconcile/pull
```

Không cần tạo thêm bảng local riêng. Request tối thiểu của `reconcile/check` chỉ cần `serial`, `uid`, `ip_address`. Nếu không gửi `from_scan_at/to_scan_at`, server tự kiểm từ lần check gần nhất đến thời điểm hiện tại. Trước khi check tối thiểu, local nên gửi heartbeat để server có tổng local mới nhất. Nếu muốn server so sánh chi tiết, máy local dùng dữ liệu trong `local_scan_records` và `local_scan_led_items` để tạo manifest gửi thêm trong `reconcile/check`.

Khi `reconcile/check` trả `SYNC_RECONCILE_DIFF_FOUND`, local hiển thị cho người dùng chọn:

- `Sync theo Local`: lấy các record server thiếu rồi gửi bằng `POST /api/sync/batches/submit`.
- `Sync theo Server`: gọi `POST /api/sync/reconcile/pull`, sau đó upsert lại `local_scan_records` và `local_scan_led_items` theo `local_scan_id`.

Bảng local nên ghi:

- `api_request_logs` cho request/response check và pull.
- `local_notifications` nếu có lệch dữ liệu hoặc có record bị ghi đè.
- `local_scan_records.sync_status = 'SYNCED'` sau khi pull hoặc batch thành công.
- `local_app_settings.local_runtime_status = 'SYNCING'` trong lúc đang sync, sau đó trả về `READY` nếu không còn lỗi chặn.

### Command polling

API liên quan:

```txt
GET  /api/machines/commands/poll?serial=...&uid=...
POST /api/machines/commands/{id}/ack
```

Bảng local nên ghi:

- `command_inbox`
- `local_notifications` nếu command là `SHOW_MESSAGE`
- `api_request_logs`

## 10. Insert scan local tối thiểu

Ví dụ tạo record local OK trước khi submit server:

```sql
SET search_path TO local_qr, public;

INSERT INTO local_scan_records (
  local_scan_id,
  machine_code,
  profile_id,
  profile_version,
  duplicate_key,
  full_code_raw,
  full_chassis_segment,
  full_chassis_code,
  full_before_vendor,
  full_vendor_char,
  full_led_code,
  full_factory_code,
  full_after_factory,
  chassis_scan_raw,
  full_code_json,
  led_scans_json,
  local_status,
  sync_status,
  scan_at
)
VALUES (
  'LS-LOCAL01-20260713-000001',
  'LOCAL01',
  1,
  1,
  '1F1SX880447',
  'VN39BN9658567A1F1S58282ADZLVX880447',
  'BN9658567A',
  'BN96-58567A',
  '1F1',
  'S',
  'BN96-58282A',
  'DZLV',
  'X880447',
  'BN96-58567A',
  '{"raw":"VN39BN9658567A1F1S58282ADZLVX880447","prefix":"VN39","chassis_code":"BN96-58567A","before_vendor":"1F1","vendor_char":"S","led_code":"BN96-58282A","factory_code":"DZLV","after_factory":"X880447"}'::jsonb,
  '[{"slot":1,"index":1,"raw":"000000000000001S8282AX","lot_no":"000000000000001","vendor_char":"S","suffix":"8282A","status":"OK"}]'::jsonb,
  'OK',
  'PENDING',
  now()
)
RETURNING id, local_scan_id;
```

Ví dụ thêm LED item:

```sql
SET search_path TO local_qr, public;

INSERT INTO local_scan_led_items (
  scan_id,
  local_scan_id,
  led_slot,
  led_index,
  led_scan_raw,
  led_lot_no,
  vendor_char,
  led_suffix,
  local_status
)
SELECT
  id,
  local_scan_id,
  1,
  1,
  'LED_SCAN_RAW_SAMPLE',
  'LEDLOT999',
  'A',
  '999',
  'OK'
FROM local_scan_records
WHERE local_scan_id = 'LS-LOCAL01-20260713-000001';
```

## 11. Update kết quả sau submit server

Nếu server trả OK:

```sql
SET search_path TO local_qr, public;

UPDATE local_scan_records
SET
  server_code = 'SERVER_OK',
  server_message = 'Scan accepted',
  server_scan_id = 123,
  server_status = 'OK',
  final_status = 'OK',
  final_ng_reason = NULL,
  sync_status = 'SYNCED',
  last_sync_at = now(),
  last_error_code = NULL,
  last_error_message = NULL
WHERE local_scan_id = 'LS-LOCAL01-20260713-000001';
```

Nếu server trả duplicate:

```sql
SET search_path TO local_qr, public;

UPDATE local_scan_records
SET
  server_code = 'SERVER_DUPLICATE',
  server_message = 'Duplicate detected by server',
  server_status = 'NG',
  final_status = 'NG',
  final_ng_reason = 'SERVER_DUPLICATE',
  sync_status = 'SYNCED',
  last_sync_at = now()
WHERE local_scan_id = 'LS-LOCAL01-20260713-000001';
```

Nếu mất mạng:

```sql
SET search_path TO local_qr, public;

UPDATE local_scan_records
SET
  server_code = NULL,
  server_message = NULL,
  server_status = 'PENDING',
  final_status = 'PENDING_SERVER',
  sync_status = 'FAILED_RETRYABLE',
  sync_attempt_count = sync_attempt_count + 1,
  next_retry_at = now() + interval '30 seconds',
  last_error_code = 'SERVER_DISCONNECTED',
  last_error_message = 'Cannot connect to server API'
WHERE local_scan_id = 'LS-LOCAL01-20260713-000001';
```

## 12. Quy tắc trạng thái

### `local_status`

```txt
OK = local parse và local rule pass
NG = local parse hoặc local rule fail
```

### `server_status`

```txt
PENDING = chưa gửi server hoặc đang chờ
OK      = server chấp nhận
NG      = server trả NG, thường do duplicate hoặc rule server
SKIPPED = server bỏ qua record trong batch
UNKNOWN = có response bất thường, cần kiểm tra log
```

### `final_status`

```txt
OK             = local OK và server OK
NG             = local NG hoặc server NG
PENDING        = chưa đủ dữ liệu để kết luận
PENDING_SERVER = local đã có record nhưng chưa sync server thành công
```

### `sync_status`

```txt
LOCAL_ONLY       = chỉ lưu local, không cần gửi server
PENDING          = cần gửi server
SYNCING          = đang gửi server
SYNCED           = đã đồng bộ xong
FAILED_RETRYABLE = lỗi tạm thời, có thể retry
FAILED_BLOCKED   = lỗi cấu hình hoặc payload, cần người xử lý
```

### `local_runtime_status`

Đây là trạng thái tổng hợp để UI Python local hiển thị ở góc màn hình hoặc header. Mỗi lần đổi trạng thái, local nên cập nhật đồng thời:

- `local_app_settings.local_runtime_status`
- `local_app_settings.local_status_message`
- `local_app_settings.local_status_updated_at`

```txt
BOOTING          = app local vừa mở, đang đọc cấu hình và kiểm server
SERVER_OFFLINE   = không gọi được server hoặc health timeout
NOT_REGISTERED   = serial/uid chưa có trên server
REGISTERING      = đang gửi register-request
WAITING_LICENSE  = request đã gửi, server chưa import/kích hoạt license
WAITING_APPROVAL = license đã kích hoạt, đang chờ admin/engineer/dev duyệt máy
REJECTED         = server từ chối request định danh
READY            = đã định danh, đã có config, sẵn sàng scan
SCANNING         = đang xử lý một lượt scan
SYNCING          = đang gửi scan pending hoặc batch sync
BLOCKED          = lỗi chặn vận hành như sai định danh, machine inactive, thiếu profile
ERROR            = lỗi runtime/local DB/cấu hình bất thường
```

Mapping gợi ý từ API:

| API/code | `local_runtime_status` | Message gợi ý |
| --- | --- | --- |
| Health timeout | `SERVER_OFFLINE` | Không kết nối được server, dữ liệu sẽ lưu pending. |
| `MACHINE_IDENTITY_NOT_REGISTERED` | `NOT_REGISTERED` | Máy chưa gửi yêu cầu định danh. |
| Đang gọi `POST /register-request` | `REGISTERING` | Đang gửi yêu cầu định danh lên server. |
| `MACHINE_REGISTER_PENDING` + `license_activated_at = null` | `WAITING_LICENSE` | Đã gửi yêu cầu, đang chờ import license. |
| `MACHINE_REGISTER_PENDING` + có `license_activated_at` | `WAITING_APPROVAL` | License đã kích hoạt, đang chờ duyệt máy. |
| `MACHINE_REGISTER_REJECTED` | `REJECTED` | Yêu cầu định danh bị từ chối. |
| `MACHINE_IDENTITY_APPROVED` và config load OK | `READY` | Máy sẵn sàng scan. |
| Đang gửi batch pending | `SYNCING` | Đang đồng bộ dữ liệu pending. |
| `MACHINE_NOT_FOUND`, `MACHINE_IDENTITY_MISMATCH`, không có profile active | `BLOCKED` | Lỗi cấu hình/định danh, cần kiểm tra server. |

## 13. Query runtime hay dùng

Lấy trạng thái hiển thị hiện tại của máy local:

```sql
SET search_path TO local_qr, public;

SELECT *
FROM v_local_runtime_status;
```

Lấy các scan cần sync:

```sql
SET search_path TO local_qr, public;

SELECT *
FROM v_pending_sync_scans
WHERE next_retry_at IS NULL OR next_retry_at <= now()
LIMIT 100;
```

Đếm pending sync:

```sql
SET search_path TO local_qr, public;

SELECT COUNT(*) AS pending_sync
FROM local_scan_records
WHERE sync_status IN ('PENDING', 'FAILED_RETRYABLE', 'SYNCING');
```

Lấy profile active:

```sql
SET search_path TO local_qr, public;

SELECT *
FROM v_active_profiles
ORDER BY profile_id;
```

Lấy notification chưa đọc:

```sql
SET search_path TO local_qr, public;

SELECT *
FROM local_notifications
WHERE status = 'NEW'
ORDER BY created_at DESC
LIMIT 50;
```

## 14. Lưu ý khi giao cho đội local

Khi gửi cho người code máy local, nên gửi kèm:

```txt
document/10-huong-dan-api-may-local-python.md
document/11-sql-khoi-tao-db-may-local-python-postgres.md
```

File số 10 giải thích API cần gọi. File số 11 là SQL tạo database local PostgreSQL.

WebSocket runtime trong file số 10 không yêu cầu thay đổi schema local. Máy local chỉ cần thêm Socket.IO client ở code Python, còn phiên chạy, đổi mã hàng, OK/NG theo phiên và dấu vết reconnect đều được lưu ở database server.

Trước khi chạy thật, người code local cần sửa:

- Password PostgreSQL.
- `machine_code`.
- `machine_serial`.
- `machine_uid`.
- `machine_license_key` nếu local muốn tự lưu license raw để đối chiếu; register request không cần gửi field này.
- `server_host`.
- `api_port` nếu server không dùng port `3979`.
- `factory_code_default` nếu nhà máy dùng mã khác.

Không chạy script này vào database server production nếu mục tiêu chỉ là tạo database local.
