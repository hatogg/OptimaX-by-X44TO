# Безпека · Security

## Українська

OptimaX працює з правами адміністратора й змінює систему, тож вразливості в ньому важливі.

**Як повідомити.** Не відкривайте публічний issue. Скористайтеся приватним звітом: вкладка **Security** цього репозиторію → **Report a vulnerability**. Опишіть, що саме вразливе, як це відтворити і на якій версії. Відповімо протягом тижня й домовимося, коли розкривати подробиці.

**Що вважається вразливістю:** підвищення прав через OptimaX чи його задачі планувальника, підміна файлів, які запускає програма (PresentMon, інсталятор оновлення, OptimaX-Rescue.cmd), обхід перевірки сертифіката в DNS-over-HTTPS, доступ до API фільтра реклами з іншого комп'ютера, витік особистих даних у звіті.

**Підтримувані версії:** лише остання версія з [релізів](https://github.com/hatogg/OptimaX-by-X44TO/releases/latest).

**Перевірка файлів:** контрольні суми кожного релізу — у `SHA256SUMS.txt`:

```powershell
Get-FileHash .\OptimaX-Setup-6.3.4.exe -Algorithm SHA256
```

## English

OptimaX runs with administrator rights and changes the system, so vulnerabilities in it matter.

**How to report.** Don't open a public issue. Use a private report: the repository's **Security** tab → **Report a vulnerability**. Describe what is vulnerable, how to reproduce it and on which version. We'll answer within a week and agree on when to disclose the details.

**What counts as a vulnerability:** privilege escalation through OptimaX or its scheduled tasks, tampering with files the program runs (PresentMon, the update installer, OptimaX-Rescue.cmd), bypassing certificate checks in DNS-over-HTTPS, access to the ad blocker API from another computer, personal data leaking into the report.

**Supported versions:** only the latest version from [releases](https://github.com/hatogg/OptimaX-by-X44TO/releases/latest).

**Verifying files:** checksums of every release are in `SHA256SUMS.txt`:

```powershell
Get-FileHash .\OptimaX-Setup-6.3.4.exe -Algorithm SHA256
```
