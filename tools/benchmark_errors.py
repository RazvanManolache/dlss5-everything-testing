"""Prefer an observed runtime error over a generic failed-route status."""


def failure_reason(result):
    error=str(result.get('error') or '')
    diagnostics=result.get('diagnostics') or result.get('processing') or {}
    if diagnostics.get('phase')==5 and error==diagnostics.get('status'):
        messages=diagnostics.get('reshade_messages') or result.get('reshade_messages') or []
        for message in reversed(messages):
            _,separator,detail=message.partition('| ERROR |')
            if separator and detail.strip():return detail.strip()
    status=diagnostics.get('status')
    if (error.startswith('No enhanced presentation within ') and diagnostics.get('execution_mode')=='not_started'
        and status and status==diagnostics.get('fallback_reason')):
        return error+': '+status
    return error
