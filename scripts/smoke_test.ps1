$loginBody = '{"reg_no":"128999001","name":"SmokeTest","year":2,"branch":"CSE(Core)"}'
$loginResp = curl.exe -s -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:3000/api/login -H "Content-Type: application/json" -d $loginBody
Write-Host "LOGIN: $loginResp"

$resumeResp = curl.exe -s -c cookies.txt -b cookies.txt http://127.0.0.1:3000/api/resume
Write-Host "RESUME: $resumeResp"

$stateResp = curl.exe -s -c cookies.txt -b cookies.txt http://127.0.0.1:3000/api/quiz/state
Write-Host "STATE (first 100): $($stateResp.Substring(0,[Math]::Min(100,$stateResp.Length)))"

$ansBody = '{"question_no":1,"option":"B"}'
$ansResp = curl.exe -s -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:3000/api/quiz/answer -H "Content-Type: application/json" -d $ansBody
Write-Host "ANSWER: $ansResp"

$subResp = curl.exe -s -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:3000/api/quiz/submit
Write-Host "SUBMIT: $subResp"

$resumeAfter = curl.exe -s -c cookies.txt -b cookies.txt http://127.0.0.1:3000/api/resume
Write-Host "RESUME_AFTER_SUBMIT: $resumeAfter"

Remove-Item cookies.txt -ErrorAction SilentlyContinue
