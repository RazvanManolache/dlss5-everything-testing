"""Public display names. Stored renderer and execution identifiers stay unchanged."""

RENDERERS = {'native': 'Native', 'phoenix': 'Phoenix DLSS5', 'nvidia': 'NVIDIA DLSS5'}
EXECUTIONS = {'x86-driver': 'x86 Phoenix DLSS5 + native driver'}


def renderer_label(identifier):
    return RENDERERS.get(identifier, identifier)


def execution_label(identifier, recorded=None):
    return EXECUTIONS.get(identifier, recorded)
