$ErrorActionPreference = "Continue"
$BASE = "http://localhost:8000/api"
$PASS = 0
$FAIL = 0
$TOKEN = $null

function Invoke-API([string]$method, [string]$path, $body=$null) {
    try {
        $uri = $BASE + $path
        $params = @{ Uri = $uri; Method = $method; UseBasicParsing = $true; TimeoutSec = 8 }
        if ($body) { $params.Body = ($body | ConvertTo-Json -Compress); $params.ContentType = "application/json; charset=utf-8" }
        if ($TOKEN) { $params.Headers = @{ Authorization = "Bearer $TOKEN" } }
        $r = Invoke-WebRequest @params
        $obj = $r.Content | ConvertFrom-Json
        $ok = ($r.StatusCode -eq 200 -and $obj.code -eq 0)
        Write-Host "  " -NoNewline
        if ($ok) { Write-Host "[PASS]" -ForegroundColor Green -NoNewline; $script:PASS++ }
        else     { Write-Host "[FAIL]" -ForegroundColor Red -NoNewline; $script:FAIL++; return }
        Write-Host " $method $path -> 200"
    } catch {
        $err = $_.Exception
        $code = if ($err.Response) { $err.Response.StatusCode.value__ } else { "ERROR" }
        Write-Host "  [FAIL]" -ForegroundColor Red -NoNewline
        Write-Host " $method $path -> $code : $($err.Message)"
        $script:FAIL++
    }
}

# ===== Step 1: Login =====
Write-Host "===== Step 1: Auth ====="
$loginBody = @{ username = "admin"; password = "admin123" }
$r = Invoke-WebRequest -Uri "$BASE/auth/login" -Method POST -Body ($loginBody | ConvertTo-Json -Compress) -ContentType "application/json" -UseBasicParsing
$TOKEN = ($r.Content | ConvertFrom-Json).data.access_token
Write-Host "  [OK] Token obtained"

Invoke-API "GET" "/auth/me"
Invoke-API "GET" "/auth/menu"

# ===== Step 2: Dict & Notifications =====
Write-Host "===== Step 2: Dict & Notifications ====="
Invoke-API "GET" "/dict/all"
Invoke-API "GET" "/notifications"

# ===== Step 3: Operators =====
Write-Host "===== Step 3: Operators ====="
Invoke-API "GET" ("/operators?page_index=1&page_size=20")
Invoke-API "POST" "/operators" @{name="test-op";category="fine-tune"}
Invoke-API "GET" ("/operators/plaza?page_index=1&page_size=12")

# ===== Step 4: Datasets =====
Write-Host "===== Step 4: Datasets ====="
Invoke-API "GET" ("/datasets?page_index=1&page_size=20")
Invoke-API "POST" "/datasets" @{name="test-ds";data_type="SFT"}
Invoke-API "GET" ("/datasets/plaza?page_index=1&page_size=12")

# ===== Step 5: Models =====
Write-Host "===== Step 5: Models ====="
Invoke-API "GET" ("/models?page_index=1&page_size=12")
Invoke-API "POST" "/models" @{name="test-model";model_type="dialogue"}
Invoke-API "GET" ("/models/plaza?page_index=1&page_size=12")
Invoke-API "POST" "/models/model-1/import"

# ===== Step 6: Training =====
Write-Host "===== Step 6: Training ====="
Invoke-API "GET" ("/train-tasks?page_index=1&page_size=20")
Invoke-API "POST" "/train-tasks" @{name="test-task";task_type="fine_tune"}
Invoke-API "GET" "/train-tasks/task-1"
Invoke-API "POST" "/train-tasks/task-1/submit"
Invoke-API "GET" ("/train-tasks/task-1/logs?tail=50")
Invoke-API "GET" "/train-tasks/task-1/metrics"

# ===== Step 7: Deployments =====
Write-Host "===== Step 7: Deployments ====="
Invoke-API "GET" ("/deployments?page_index=1&page_size=20")
Invoke-API "POST" "/deployments" @{name="test-deploy";model_id="model-1"}
Invoke-API "POST" "/deployments/deploy-1/start"
Invoke-API "POST" "/deployments/deploy-1/test" @{prompt="hello"}

# ===== Step 8: Evaluations =====
Write-Host "===== Step 8: Evaluations ====="
Invoke-API "GET" ("/evaluations?page_index=1&page_size=20")
Invoke-API "POST" "/evaluations" @{name="test-eval"}
Invoke-API "GET" "/evaluations/eval-1/report"

# ===== Summary =====
Write-Host ""
Write-Host "===== Summary ====="
Write-Host "  PASS: $PASS" -ForegroundColor Green
Write-Host "  FAIL: $FAIL" -ForegroundColor $(if ($FAIL -gt 0) { "Red" } else { "Green" })
