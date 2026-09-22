from windows_mcp.powershell import PowerShellExecutor
from windows_mcp.powershell.utils import ps_quote, ps_quote_for_xml

__all__ = [
    "send_notification",
]

_BLOCKED_REASONS = {
    "DisabledForApplication": "notifications are turned off for this app in Windows Settings",
    "DisabledForUser": "notifications are turned off for all apps in Windows Settings",
    "DisabledByGroupPolicy": "notifications are turned off by group policy",
    "DisabledByManifest": "this app is not allowed to show notifications",
}


def send_notification(title: str, message: str, app_id: str) -> str:
    """Send a Windows toast notification with a title and message.

    Args:
        title: The title of the notification.
        message: The message of the notification.
        app_id: The valid Application User Model ID of the toast notification.
            Required to display the notification in a specific app.

    Returns:
        A string indicating the result of the notification.

    Notes:
        The MCP client MUST provide an App ID because Windows uses it as the
        app identity for desktop toast notifications, and it MUST match a
        registered shortcut/AppUserModelID.
    """
    safe_title = ps_quote_for_xml(title)
    safe_message = ps_quote_for_xml(message)
    safe_app_id = ps_quote(app_id)

    ps_script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null\n"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null\n"
        f"$notifTitle = {safe_title}\n"
        f"$notifMessage = {safe_message}\n"
        f"$appId = {safe_app_id}\n"
        '$template = @"\n'
        "<toast>\n"
        "    <visual>\n"
        '        <binding template="ToastGeneric">\n'
        "            <text>$notifTitle</text>\n"
        "            <text>$notifMessage</text>\n"
        "        </binding>\n"
        "    </visual>\n"
        "</toast>\n"
        '"@\n'
        "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
        "$xml.LoadXml($template)\n"
        # Windows accepts any id and silently drops toasts from unknown apps, so check first.
        "$known = @(Get-StartApps | Where-Object AppID -eq $appId).Count -gt 0 -or "
        '(Test-Path -LiteralPath "HKCU:\\Software\\Classes\\AppUserModelId\\$appId") -or '
        '(Test-Path -LiteralPath "HKLM:\\Software\\Classes\\AppUserModelId\\$appId")\n'
        "if (-not $known) { Write-Output 'UNKNOWN_APP_ID'; exit 3 }\n"
        "$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId)\n"
        '$setting = "$($notifier.Setting)"\n'
        "if ($setting -ne 'Enabled') { Write-Output \"BLOCKED:$setting\"; exit 4 }\n"
        "$toast = New-Object Windows.UI.Notifications.ToastNotification $xml\n"
        "$notifier.Show($toast)"
    )
    # Use Windows PowerShell (5.1) explicitly because the WinRT toast APIs are not available in PowerShell 7+ (pwsh).
    response, status = PowerShellExecutor.execute_command(ps_script, shell="powershell")
    response = response.strip()
    if status == 3 and response == "UNKNOWN_APP_ID":
        return (
            f"Error: app_id {app_id!r} is not an installed app, so Windows would drop the "
            "toast. Use an AppID listed by Get-StartApps, e.g. "
            r"'{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'."
        )
    if status == 4 and response.startswith("BLOCKED:"):
        setting = response.split(":", 1)[1]
        reason = _BLOCKED_REASONS.get(setting, f"Windows reports the setting {setting!r}")
        return f"Error: notification not shown: {reason}."
    if status != 0:
        return f"Error sending notification: {response[:300]}"
    # Focus / Do Not Disturb has no supported API to read, so say so rather than imply delivery.
    return (
        f'Notification sent: "{title}" - {message}. If Do Not Disturb (Focus) is on, '
        "Windows puts it straight into the notification centre without a pop-up."
    )
