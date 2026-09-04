from __future__ import annotations

import html
import json
import os
import subprocess
import tempfile
from pathlib import Path


class OutlookIntegrationError(RuntimeError):
    pass


class OutlookService:
    """Создание черновика письма в классическом Outlook for Windows.

    В проекте больше нет обязательной зависимости от ``pywin32``. Интеграция
    использует штатный Windows PowerShell + Outlook COM, поэтому на обычном ПК
    с Classic Outlook дополнительный Python-пакет устанавливать не требуется.

    Новый Outlook for Windows не предоставляет классический Outlook COM Object
    Model. В этом случае показываем понятное сообщение вместо совета установить
    pywin32, который проблему нового Outlook всё равно не решит.
    """

    _POWERSHELL_NAMES = ("powershell.exe", "powershell")

    @staticmethod
    def _ensure_windows():
        if os.name != "nt":
            raise OutlookIntegrationError(
                "Интеграция с Outlook доступна только в Windows."
            )

    @classmethod
    def _powershell_executable(cls) -> str:
        cls._ensure_windows()
        # subprocess сам найдёт powershell.exe через PATH. На штатной Windows
        # он присутствует практически всегда; отдельный PowerShell 7 не нужен.
        return cls._POWERSHELL_NAMES[0]

    @staticmethod
    def text_to_html(text: str) -> str:
        escaped = html.escape(str(text or ""))
        return (
            '<div style="font-family:Segoe UI;font-size:10.5pt">'
            + escaped.replace("\n", "<br>")
            + "</div>"
        )

    @classmethod
    def _run_powershell(cls, script: str, payload: dict | None = None):
        cls._ensure_windows()
        payload_path = None
        script_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8-sig", suffix=".ps1", delete=False
            ) as ps_file:
                ps_file.write(script)
                script_path = ps_file.name

            args = [
                cls._powershell_executable(),
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
            ]

            if payload is not None:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8-sig", suffix=".json", delete=False
                ) as data_file:
                    json.dump(payload, data_file, ensure_ascii=False)
                    payload_path = data_file.name
                args.append(payload_path)

            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=creationflags,
                check=False,
            )
            stdout = (completed.stdout or "").strip()
            stderr = (completed.stderr or "").strip()
            if completed.returncode != 0:
                detail = stderr or stdout or "неизвестная ошибка PowerShell/COM"
                raise OutlookIntegrationError(detail)
            return stdout
        except FileNotFoundError as exc:
            raise OutlookIntegrationError(
                "Не найден Windows PowerShell. Интеграция с Outlook не может быть запущена."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise OutlookIntegrationError(
                "Outlook не ответил за 30 секунд. Проверьте, запущен ли Classic Outlook и настроен ли профиль почты."
            ) from exc
        finally:
            for temp_path in (payload_path, script_path):
                if temp_path:
                    try:
                        Path(temp_path).unlink(missing_ok=True)
                    except Exception:
                        pass

    def check_available(self):
        script = r'''
$ErrorActionPreference = 'Stop'
try {
    $outlook = New-Object -ComObject Outlook.Application
    $null = $outlook.GetNamespace('MAPI')
    Write-Output 'OK'
    exit 0
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
'''
        try:
            self._run_powershell(script)
            return True, (
                "Classic Outlook доступен. Дополнительный компонент pywin32 не требуется."
            )
        except OutlookIntegrationError as exc:
            return False, (
                "Не удалось подключиться к Classic Outlook. "
                "Если у вас установлен новый Outlook for Windows, его COM-интерфейс "
                "не поддерживается этой интеграцией.\n\n"
                f"Техническая причина: {exc}"
            )

    def create_draft(
        self,
        *,
        to: str,
        cc: str = "",
        subject: str,
        body: str,
        attachments=None,
    ):
        recipients = str(to or "").strip().replace(",", ";")
        if not recipients:
            raise OutlookIntegrationError("Не указаны получатели письма.")

        attachment_paths = []
        for attachment in attachments or []:
            file_path = Path(str(attachment)).expanduser().resolve()
            if not file_path.exists():
                raise OutlookIntegrationError(
                    f"Не найден файл для вложения: {file_path}"
                )
            attachment_paths.append(str(file_path))

        payload = {
            "to": recipients,
            "cc": str(cc or "").strip().replace(",", ";"),
            "subject": str(subject or ""),
            "body_html": self.text_to_html(body),
            "attachments": attachment_paths,
        }

        # Display() вызывается до подстановки HTMLBody, чтобы Outlook успел
        # добавить корпоративную подпись. Затем наш текст ставится перед ней.
        script = r'''
param([string]$PayloadPath)
$ErrorActionPreference = 'Stop'
try {
    $data = Get-Content -LiteralPath $PayloadPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $outlook = New-Object -ComObject Outlook.Application
    $mail = $outlook.CreateItem(0)
    $mail.To = [string]$data.to
    if ([string]$data.cc) { $mail.CC = [string]$data.cc }
    $mail.Subject = [string]$data.subject

    # Первый Display даёт Classic Outlook создать стандартную подпись.
    $mail.Display($false)
    Start-Sleep -Milliseconds 150
    $signature = [string]$mail.HTMLBody
    $mail.HTMLBody = ([string]$data.body_html) + '<br><br>' + $signature

    foreach ($item in @($data.attachments)) {
        if ([string]$item) {
            $null = $mail.Attachments.Add([string]$item)
        }
    }

    $mail.Display($false)
    Write-Output 'OK'
    exit 0
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
'''
        try:
            self._run_powershell(script, payload)
            return True
        except OutlookIntegrationError as exc:
            raise OutlookIntegrationError(
                "Не удалось подготовить письмо в Classic Outlook. "
                "Дополнительная установка pywin32 больше не требуется. "
                "Проверьте, что установлен именно Classic Outlook for Windows, "
                "в нём создан почтовый профиль и Outlook может открывать новые письма.\n\n"
                f"Техническая причина: {exc}"
            ) from exc
