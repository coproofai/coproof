param(
    [string]$BackendUrl = "http://localhost:5001",
    [switch]$ShowRawResponses
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Get-ExampleCases {
    param([string]$ExamplesDir)

    $exampleCases = @()
    $expectedMap = @{
        "basic_arithmetic.lean" = $true
        "function_properties.lean" = $false
        "induction_proof.lean" = $false
        "invalid_proof.lean" = $true
        "list_operations.lean" = $false
        "propositional_logic.lean" = $false
    }

    if (-not (Test-Path $ExamplesDir)) {
        Write-Host "Examples directory not found: $ExamplesDir" -ForegroundColor Yellow
        return $exampleCases
    }

    $files = Get-ChildItem -Path $ExamplesDir -Filter "*.lean" | Sort-Object Name

    foreach ($file in $files) {
        $content = Get-Content -Path $file.FullName -Raw
        $containsSorry = $content -match "\bsorry\b"

        $expectedValid = $true
        if ($expectedMap.ContainsKey($file.Name)) {
            $expectedValid = [bool]$expectedMap[$file.Name]
        }
        elseif ($containsSorry) {
            $expectedValid = $true
        }

        $exampleCases += @{
            name = "Example file: $($file.Name)"
            expectedValid = $expectedValid
            code = $content
            source = $file.FullName
            hasSorry = $containsSorry
        }
    }

    return $exampleCases
}

function Invoke-RoundtripCase {
    param(
        [string]$Name,
        [string]$Code,
        [bool]$ExpectedValid
    )

    Write-Step "Running case: $Name"

    try {
        $verifyBody = @{ code = $Code } | ConvertTo-Json
        $verifyBodyBytes = [System.Text.Encoding]::UTF8.GetBytes($verifyBody)
        $verifyResp = Invoke-RestMethod -Method POST -Uri "$BackendUrl/api/v1/projects/tools/verify-snippet/public" -ContentType "application/json; charset=utf-8" -Body $verifyBodyBytes

        $isValid = $verifyResp.result.valid -eq $true
        $matchExpectation = ($isValid -eq $ExpectedValid)
        $processingTime = -1.0
        if ($null -ne $verifyResp.result.processing_time_seconds) {
            $processingTime = [double]$verifyResp.result.processing_time_seconds
        }
        $roundtripTime = -1.0
        if ($null -ne $verifyResp.result.roundtrip_time_seconds) {
            $roundtripTime = [double]$verifyResp.result.roundtrip_time_seconds
        }
        $timingSource = if ($null -ne $verifyResp.result.timing_source) { [string]$verifyResp.result.timing_source } else { "unknown" }

        if ($matchExpectation) {
            Write-Host "PASS: $Name (valid=$isValid, expected=$ExpectedValid, lean_time=${processingTime}s, roundtrip_time=${roundtripTime}s, source=$timingSource)" -ForegroundColor Green
        }
        else {
            Write-Host "FAIL: $Name (valid=$isValid, expected=$ExpectedValid, lean_time=${processingTime}s, roundtrip_time=${roundtripTime}s, source=$timingSource)" -ForegroundColor Yellow
        }

        return @{
            name = $Name
            valid = $isValid
            expectedValid = $ExpectedValid
            matches = $matchExpectation
            processingTimeSeconds = $processingTime
            roundtripTimeSeconds = $roundtripTime
            timingSource = $timingSource
            errorCount = @($verifyResp.result.errors).Count
            response = $verifyResp
            error = $null
        }
    }
    catch {
        Write-Host "ERROR: $Name -> $($_.Exception.Message)" -ForegroundColor Red
        return @{
            name = $Name
            valid = $false
            expectedValid = $ExpectedValid
            matches = $false
            processingTimeSeconds = -1
            roundtripTimeSeconds = -1
            timingSource = "error"
            errorCount = -1
            response = $null
            error = $_.Exception.Message
        }
    }
}

try {
    $examplesDir = Join-Path $PSScriptRoot "..\..\lean\examples"

    $cases = @(
        @{
            name = "Basic theorem"
            expectedValid = $true
            code = @"
theorem demo_roundtrip : True := by
  trivial
"@
        },
        @{
            name = "Mathlib arithmetic (Nat.add_comm)"
            expectedValid = $true
            code = @"
import Mathlib

example (a b : Nat) : a + b = b + a := by
  simpa using Nat.add_comm a b
"@
        },
        @{
            name = "Mathlib set-theory (subset reflexive)"
            expectedValid = $true
            code = @"
import Mathlib

example (s : Set Nat) : Set.Subset s s := by
    intro x hx
    exact hx
"@
        },
        @{
            name = "Bad proof (wrong theorem application)"
            expectedValid = $false
            code = @"
import Mathlib

example (a b : Nat) : a + b = b + a := by
  simpa using Nat.mul_comm a b
"@
        },
        @{
            name = "Bad proof (unfinished sorry)"
                        expectedValid = $true
            code = @"
import Mathlib

example (n : Nat) : n = n := by
  sorry
"@
        },
        @{
            name = "Bad proof (type mismatch)"
            expectedValid = $false
            code = @"
example : True := by
  exact (0 : Nat)
"@
        }
    )

    $exampleCases = Get-ExampleCases -ExamplesDir $examplesDir
    if ($exampleCases.Count -gt 0) {
        Write-Step "Loaded Lean examples"
        $exampleCases | ForEach-Object {
            [PSCustomObject]@{
                Case = $_.name
                HasSorry = $_.hasSorry
                Expected = $_.expectedValid
            }
        } | Format-Table -AutoSize

        $cases += $exampleCases
    }

    $results = @()
    foreach ($case in $cases) {
        $results += Invoke-RoundtripCase -Name $case.name -Code $case.code -ExpectedValid $case.expectedValid
    }

    Write-Step "Roundtrip summary"
    $results | ForEach-Object {
        [PSCustomObject]@{
            Case = $_.name
            Valid = $_.valid
            Expected = $_.expectedValid
            Match = $_.matches
            TimeSec = $_.processingTimeSeconds
            RoundtripSec = $_.roundtripTimeSeconds
            TimingSource = $_.timingSource
            ErrorCount = $_.errorCount
            Error = if ($_.error) { $_.error } else { "" }
        }
    } | Format-Table -AutoSize

    $timings = @()
    foreach ($r in $results) {
        if ($null -ne $r.processingTimeSeconds -and $r.processingTimeSeconds -ge 0) {
            $timings += [double]$r.processingTimeSeconds
        }
    }

    if ($timings.Count -gt 0) {
        $avgTime = [Math]::Round((($timings | Measure-Object -Average).Average), 3)
        $minTime = [Math]::Round((($timings | Measure-Object -Minimum).Minimum), 3)
        $maxTime = [Math]::Round((($timings | Measure-Object -Maximum).Maximum), 3)

        Write-Step "Timing metrics"
        Write-Host "Average: ${avgTime}s | Min: ${minTime}s | Max: ${maxTime}s"
    }

    if ($ShowRawResponses) {
        Write-Step "Raw backend responses"
        foreach ($r in $results) {
            if ($r.response) {
                Write-Host "`n--- $($r.name) ---"
                $r.response | ConvertTo-Json -Depth 10
            }
        }
    }

    if (($results | Where-Object { -not $_.matches }).Count -eq 0) {
        Write-Host "`nTest suite success: all cases matched expectations (including bad-proof handling)." -ForegroundColor Green
        exit 0
    }

    Write-Host "`nTest suite completed with mismatches. Review summary table." -ForegroundColor Yellow
    exit 2
}
catch {
    Write-Host "`nRoundtrip failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
