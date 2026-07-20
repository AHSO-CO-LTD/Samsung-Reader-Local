<#
.SYNOPSIS
    Setup script cho Local Reader Monitor — cài PostgreSQL (nếu chưa có) +
    tạo role/database/schema + sinh local_db_config.json.

.DESCRIPTION
    Chạy 1 lần khi cài đặt máy production mới. Idempotent — chạy lại an
    toàn nhiều lần (không tạo trùng role/database, không đổi mật khẩu nếu
    không cần, không ghi đè local_db_config.json đã có sẵn).

    Vị trí: nằm CẠNH LocalReaderMonitor.exe (cùng thư mục giải nén từ gói
    release) — đọc schema.sql từ _internal\db\schema.sql cạnh nó, ghi
    local_db_config.json cũng cạnh nó.

    Mật khẩu CỐ ĐỊNH, GIỐNG NHAU trên mọi máy (quyết định có chủ đích, xem
    docs/deploy.md mục "Thông tin quản trị"): PostgreSQL ở đây chỉ chạy
    nội bộ (127.0.0.1, không mở ra mạng ngoài) — ưu tiên "ai cũng tra được
    đúng mật khẩu khi cần" hơn là mỗi máy 1 mật khẩu ngẫu nhiên rồi mất dấu
    nếu JSON bị sửa/xoá nhầm. Có thể đổi 2 giá trị mặc định bên dưới nếu
    muốn, miễn GIỮ NGUYÊN + GIỐNG NHAU trên mọi máy và cập nhật lại
    docs/deploy.md theo đúng giá trị mới.

.PARAMETER AppRoleName
    Tên role PostgreSQL app dùng để kết nối hàng ngày. KHÔNG đổi giá trị
    này khi chạy thật trên máy production — chỉ đổi lúc tự test an toàn
    (dùng tên khác để không đụng role thật samsung_qr_local_user).

.PARAMETER AppDbName
    Tên database local. Tương tự AppRoleName — chỉ đổi lúc tự test.

.PARAMETER PgSuperPassword
    Mật khẩu superuser PostgreSQL (role `postgres`) — dùng lúc cài đặt lần
    đầu (nếu máy chưa có PostgreSQL) + về sau nếu cần thao tác quản trị tay
    qua pgAdmin/psql.

.PARAMETER AppRolePassword
    Mật khẩu role app — chính là giá trị sẽ nằm trong local_db_config.json.

.PARAMETER PgPort
    Cổng PostgreSQL. Mặc định 5432 (chuẩn PostgreSQL, không phải cổng API
    server — đừng nhầm với api_port trong server_config.json).
#>

param(
    [string]$AppRoleName = "samsung_qr_local_user",
    [string]$AppDbName = "samsung_qr_local",
    [string]$PgSuperPassword = "0123456789",
    [string]$AppRolePassword = "0123456789",
    [int]$PgPort = 5432
)

$ErrorActionPreference = "Stop"

$ExeDir = $PSScriptRoot
$SchemaPath = Join-Path $ExeDir "_internal\db\schema.sql"
$ConfigDir = Join-Path $ExeDir "config"
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
$ConfigPath = Join-Path $ConfigDir "local_db_config.json"
# File cũ (bản trước khi gộp mọi config vào thư mục config/) — nếu máy đã
# từng setup bằng bản setup.ps1 cũ, di chuyển thay vì tạo mới đè mất cấu hình.
$LegacyConfigPath = Join-Path $ExeDir "local_db_config.json"
$AppDbSchema = "local_qr"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Find-PsqlExe {
    $found = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
        Sort-Object { [int]$_.Directory.Parent.Name } -Descending |
        Select-Object -First 1
    if ($found) { return $found.FullName }

    $cmd = Get-Command psql.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    return $null
}

function Invoke-Psql {
    <#
    Chạy 1 lệnh psql, trả về text output (đã trim). Ném exception nếu
    psql thoát với exit code khác 0 — $ErrorActionPreference=Stop dừng
    toàn bộ script tại đây thay vì tiếp tục với trạng thái nửa vời.
    #>
    param(
        [Parameter(Mandatory)][string]$PsqlPath,
        [Parameter(Mandatory)][string]$Username,
        [Parameter(Mandatory)][string]$Password,
        [Parameter(Mandatory)][string]$Database,
        [string]$Command,
        [string]$File
    )

    $env:PGPASSWORD = $Password
    try {
        $args = @("-h", "127.0.0.1", "-p", $PgPort, "-U", $Username, "-d", $Database, "-v", "ON_ERROR_STOP=1", "-t", "-A")
        if ($Command) { $args += @("-c", $Command) }
        if ($File) { $args += @("-f", $File) }

        # KHÔNG dùng "2>&1" — PowerShell 5.1 bọc từng dòng stderr của native exe
        # thành ErrorRecord, khiến $ErrorActionPreference=Stop dừng cả script
        # ngay cả khi psql chỉ in NOTICE (vd "trigger ... does not exist,
        # skipping" từ DROP TRIGGER IF EXISTS trong schema.sql) chứ không thật
        # sự lỗi — verify bằng chạy thật, không đoán. Để stderr in thẳng ra
        # console (operator vẫn thấy nội dung), chỉ dựa vào $LASTEXITCODE để
        # biết psql có lỗi thật hay không.
        $output = & $PsqlPath @args
        if ($LASTEXITCODE -ne 0) {
            throw "psql failed with exit code $LASTEXITCODE — see error output above."
        }
        return ($output -join "`n").Trim()
    } finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
}

# Bọc toàn bộ phần thân trong try/catch/finally — LÝ DO: trước đây mọi lỗi
# (kể cả throw từ Invoke-Psql/exit 1 cũ) khiến cửa sổ PowerShell đóng NGAY
# LẬP TỨC khi chạy qua "Run with PowerShell" (double-click mở 1 powershell.exe
# riêng, tự đóng cửa sổ khi script kết thúc dù thành công hay lỗi) — operator
# không kịp đọc thông báo lỗi dù script ĐÃ in ra, tưởng nhầm là "crash không
# rõ lý do". finally { Read-Host } đảm bảo cửa sổ luôn dừng lại chờ Enter.
try {

######################################################################
# 1. PostgreSQL đã cài chưa?
######################################################################

Write-Step "Checking for existing PostgreSQL installation..."

$psqlPath = Find-PsqlExe
$pgFreshlyInstalled = $false

if (-not $psqlPath) {
    Write-Host "PostgreSQL not found. Attempting automatic install..."

    $installerArgs = @("--mode", "unattended", "--unattendedmodeui", "minimal", "--superpassword", $PgSuperPassword, "--serverport", $PgPort)
    $installedThisRun = $false

    # --- Cách 1: tải trực tiếp bằng Invoke-WebRequest rồi tự chạy installer ---
    # Đây là cách ƯU TIÊN, KHÔNG phải winget — vì winget có lịch sử hay KHÔNG
    # nhận đúng proxy công ty (WinRT/COM networking stack riêng, không dùng
    # chung cấu hình proxy hệ thống/WinINET) — máy khách vẫn ra được Internet
    # bình thường qua proxy, nhưng winget lại fail dù domain KHÔNG hề bị chặn.
    # Invoke-WebRequest mặc định tự dùng proxy hệ thống (WinINET) nên nhiều
    # khả năng tải được ở đúng chỗ winget đã fail — không cần domain khác.
    Write-Host "Đang tải PostgreSQL installer (qua HTTP trực tiếp, tự dùng proxy hệ thống nếu có)..."
    $installerUrl = "https://get.enterprisedb.com/postgresql/postgresql-17.7-1-windows-x64.exe"
    $installerPath = Join-Path $env:TEMP "postgresql-installer-lrm.exe"
    $downloadOk = $false
    try {
        $ProgressPreference = "SilentlyContinue"  # tắt progress bar UI của Invoke-WebRequest — chậm đáng kể khi tải file lớn qua remoting/non-interactive host
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing -TimeoutSec 180
        $downloadOk = Test-Path $installerPath
        if ($downloadOk) { Write-Host "Tải thành công." -ForegroundColor Green }
    } catch {
        Write-Host "Tải trực tiếp thất bại: $($_.Exception.Message)" -ForegroundColor Yellow
    } finally {
        $ProgressPreference = "Continue"
    }

    if ($downloadOk) {
        Write-Host "Đang cài đặt (không cần mạng ở bước này)..."
        & $installerPath @installerArgs
        Remove-Item $installerPath -ErrorAction SilentlyContinue
        $psqlPath = Find-PsqlExe
        if ($psqlPath) { $installedThisRun = $true }
    }

    # --- Cách 2: fallback winget (giữ lại — máy nào không cần proxy, hoặc
    # network khác hẳn, winget vẫn có thể là đường tắt hoạt động tốt) ---
    if (-not $psqlPath) {
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if ($winget) {
            Write-Host "Thử cài qua winget (dự phòng)..."
            & winget install --id PostgreSQL.PostgreSQL --silent `
                --accept-package-agreements --accept-source-agreements `
                --override "--mode unattended --unattendedmodeui minimal --superpassword $PgSuperPassword --serverport $PgPort"
            $psqlPath = Find-PsqlExe
            if ($psqlPath) { $installedThisRun = $true }
        }
    }

    if (-not $psqlPath) {
        Write-Host ""
        Write-Host "Automatic install did not complete successfully (đã thử cả tải trực tiếp lẫn winget)." -ForegroundColor Red
        Write-Host "Please install PostgreSQL manually:" -ForegroundColor Yellow
        Write-Host "  1. Download from: https://www.postgresql.org/download/windows/"
        Write-Host "  2. During install, set the superuser (postgres) password to:"
        Write-Host "     $PgSuperPassword"
        Write-Host "  3. Re-run this script after installation completes."
        throw "Automatic PostgreSQL install failed — see instructions above."
    }
    $pgFreshlyInstalled = $installedThisRun
    Write-Host "PostgreSQL installed successfully."
} else {
    Write-Host "Found existing PostgreSQL: $psqlPath"
}

######################################################################
# 2. Xác nhận mật khẩu superuser đúng như mong đợi
######################################################################

Write-Step "Verifying PostgreSQL superuser credentials..."

try {
    Invoke-Psql -PsqlPath $psqlPath -Username "postgres" -Password $PgSuperPassword -Database "postgres" -Command "SELECT 1" | Out-Null
    Write-Host "Superuser credentials OK."
} catch {
    Write-Host ""
    Write-Host "Cannot connect as 'postgres' with the expected password." -ForegroundColor Red
    if ($pgFreshlyInstalled) {
        Write-Host "This PostgreSQL instance was just installed by this script — this is unexpected." -ForegroundColor Red
    } else {
        Write-Host "This machine already had PostgreSQL installed with a DIFFERENT superuser password." -ForegroundColor Yellow
        Write-Host "This is not the normal flow for a clean production machine. Please resolve manually:" -ForegroundColor Yellow
        Write-Host "  - Either reset the 'postgres' role password to match `$PgSuperPassword` used here, or"
        Write-Host "  - Re-run this script with -PgSuperPassword matching the existing installation."
    }
    throw "Cannot authenticate as postgres superuser — see instructions above."
}

######################################################################
# 3. Role app
######################################################################

Write-Step "Ensuring role '$AppRoleName' exists..."

$roleExists = Invoke-Psql -PsqlPath $psqlPath -Username "postgres" -Password $PgSuperPassword -Database "postgres" `
    -Command "SELECT 1 FROM pg_roles WHERE rolname = '$AppRoleName'"

$escapedAppRolePassword = $AppRolePassword.Replace("'", "''")

if ($roleExists -eq "1") {
    Write-Host "Role already exists — resetting its password to the documented fixed value (self-healing if changed by accident)."
    Invoke-Psql -PsqlPath $psqlPath -Username "postgres" -Password $PgSuperPassword -Database "postgres" `
        -Command "ALTER ROLE $AppRoleName LOGIN PASSWORD '$escapedAppRolePassword'" | Out-Null
} else {
    Write-Host "Creating role '$AppRoleName'..."
    Invoke-Psql -PsqlPath $psqlPath -Username "postgres" -Password $PgSuperPassword -Database "postgres" `
        -Command "CREATE ROLE $AppRoleName LOGIN PASSWORD '$escapedAppRolePassword'" | Out-Null
}

######################################################################
# 4. Database
######################################################################

Write-Step "Ensuring database '$AppDbName' exists..."

$dbExists = Invoke-Psql -PsqlPath $psqlPath -Username "postgres" -Password $PgSuperPassword -Database "postgres" `
    -Command "SELECT 1 FROM pg_database WHERE datname = '$AppDbName'"

if ($dbExists -eq "1") {
    Write-Host "Database already exists — skipping creation."
} else {
    Write-Host "Creating database '$AppDbName'..."
    Invoke-Psql -PsqlPath $psqlPath -Username "postgres" -Password $PgSuperPassword -Database "postgres" `
        -Command "CREATE DATABASE $AppDbName WITH OWNER = $AppRoleName ENCODING = 'UTF8' CONNECTION LIMIT = -1" | Out-Null
}

Invoke-Psql -PsqlPath $psqlPath -Username "postgres" -Password $PgSuperPassword -Database "postgres" `
    -Command "GRANT ALL PRIVILEGES ON DATABASE $AppDbName TO $AppRoleName" | Out-Null

######################################################################
# 5. Schema (CREATE TABLE IF NOT EXISTS — chạy lại an toàn)
######################################################################

Write-Step "Applying schema ($SchemaPath)..."

if (-not (Test-Path $SchemaPath)) {
    throw "schema.sql not found at $SchemaPath — is this script sitting beside LocalReaderMonitor.exe?"
}

Invoke-Psql -PsqlPath $psqlPath -Username $AppRoleName -Password $AppRolePassword -Database $AppDbName -File $SchemaPath | Out-Null
Write-Host "Schema applied."

######################################################################
# 6. local_db_config.json (chỉ ghi nếu CHƯA có — không ghi đè máy đã setup)
######################################################################

Write-Step "Writing local_db_config.json..."

if (Test-Path $ConfigPath) {
    Write-Host "local_db_config.json already exists — leaving it untouched."
} elseif (Test-Path $LegacyConfigPath) {
    Move-Item $LegacyConfigPath $ConfigPath
    Write-Host "local_db_config.json migrated from old location (project root) to config/."
} else {
    $config = [ordered]@{
        host     = "127.0.0.1"
        port     = $PgPort
        dbname   = $AppDbName
        user     = $AppRoleName
        password = $AppRolePassword
        schema   = $AppDbSchema
    }
    $json = $config | ConvertTo-Json
    # UTF-8 KHÔNG BOM — db/local_db.py đọc bằng utf-8-sig nên chấp nhận cả
    # 2 trường hợp, nhưng không BOM vẫn là lựa chọn sạch hơn khi tự ghi mới.
    [System.IO.File]::WriteAllText($ConfigPath, $json, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "local_db_config.json created."
}

######################################################################
# Xong
######################################################################

Write-Host ""
Write-Host "Setup complete — you can now open LocalReaderMonitor.exe." -ForegroundColor Green
$exitCode = 0

} catch {
    Write-Host ""
    Write-Host "SETUP THAT BAI: $($_.Exception.Message)" -ForegroundColor Red
    $exitCode = 1
} finally {
    Write-Host ""
    Read-Host "Nhan Enter de dong cua so nay"
}

exit $exitCode
