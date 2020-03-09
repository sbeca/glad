import jinja2

import glad
from glad.config import Config, ConfigOption
from glad.generator import JinjaGenerator
from glad.generator.util import (
    strip_specification_prefix,
    collect_alias_information,
    find_extensions_with_aliases
)
from glad.parse import ParsedType
from glad.sink import LoggingSink


_CSHARP_TYPE_MAPPING = {
    'void': 'void',
    'char': 'char',
    'uchar': 'uchar',
    'float': 'float',
    'double': 'double',
    'int': 'int',
    'long': 'long',
    'int8_t': 'sbyte',
    'uint8_t': 'byte',
    'int16_t': 'short',
    'uint16_t': 'ushort',
    'int32_t': 'int',
    'int64_t': 'long',
    'uint32_t': 'uint',
    'uint64_t': 'ulong',
    'GLenum': 'GLEnum',
    'GLbitfield': 'GLEnum',
    'GLboolean': 'bool',
    'GLvoid': 'void',
    'GLbyte': 'sbyte',
    'GLchar': 'sbyte',
    'GLcharARB': 'sbyte',
    'GLubyte': 'byte',
    'GLshort': 'short',
    'GLushort': 'ushort',
    'GLhalf': 'ushort',
    'GLhalfARB': 'ushort',
    'GLhalfNV': 'ushort',
    'GLhandleARB': 'ushort',
    'GLint': 'int',
    'GLclampx': 'int',
    'GLsizei': 'int',
    'GLfixed': 'int',
    'GLuint': 'uint',
    'GLfloat': 'float',
    'GLclampf': 'float',
    'GLdouble': 'double',
    'GLclampd': 'double',
    'GLeglClientBufferEXT': 'IntPtr',
    'GLeglImageOES': 'IntPtr',
    'GLintptr': 'IntPtr',
    'GLintptrARB': 'IntPtr',
    'GLvdpauSurfaceNV': 'IntPtr',
    'GLsizeiptr': 'IntPtr',
    'GLsizeiptrARB': 'IntPtr',
    'GLsync': 'IntPtr',
    'GLint64': 'long',
    'GLint64EXT': 'long',
    'GLuint64': 'ulong',
    'GLuint64EXT': 'ulong',
    'GLDEBUGPROC': 'DebugProc',
    'GLDEBUGPROCARB': 'DebugProc',
    'GLDEBUGPROCKHR': 'DebugProc',
    'GLDEBUGPROCAMD': 'DebugProcAMD',
    'GLVULKANPROCNV': 'VulkanDebugProcNV',
}

_CSHARP_KEYWORD_MAPPING = {
    'in': '@in',
    'out': '@out',
    'params': '@params',
    'string': '@string',
    'ref': '@ref',
}


def enum_type(enum, feature_set):
    if enum.alias and enum.value is None:
        aliased = feature_set.find_enum(enum.alias)
        if aliased is None:
            raise ValueError('unable to resolve enum alias {} of enum {}'.format(enum.alias, enum))
        enum = aliased

    # if the value links to another enum, resolve the enum right now
    if enum.value is not None:
        # enum = feature_set.find_enum(enum.value, default=enum)
        referenced = feature_set.find_enum(enum.value)
        # TODO currently every enum with a parent type is u32
        if referenced is not None and referenced.parent_type is not None:
            return 'u32'

    # we could return GLenum and friends here
    # but thanks to type aliasing we don't have to
    # this makes handling types for different specifications
    # easier, since we don't have to swap types. GLenum -> XXenum.
    if enum.type:
        return {
            'ull': 'u64',
        }.get(enum.type, 'std::os::raw::c_uint')

    if enum.value.startswith('0x'):
        return 'u64' if len(enum.value[2:]) > 8 else 'std::os::raw::c_uint'

    if enum.name in ('GL_TRUE', 'GL_FALSE'):
        return 'std::os::raw::c_uchar'

    if enum.value.startswith('-'):
        return 'std::os::raw::c_int'

    if enum.value.endswith('f'):
        return 'std::os::raw::c_float'

    if enum.value.startswith('"'):
        # TODO figure out correct type
        return '&str'

    if enum.value.startswith('(('):
        # Casts: '((Type)value)' -> 'Type'
        raise NotImplementedError

    if enum.value.startswith('EGL_CAST'):
        # EGL_CAST(type,value) -> type
        return enum.value.split('(', 1)[1].split(',')[0]

    return 'std::os::raw::c_uint'


def enum_value(enum, feature_set):
    if enum.alias and enum.value is None:
        enum = feature_set.find_enum(enum.alias)

    # basically an alias to another enum (value contains another enum)
    # resolve it here and adjust value accordingly.
    referenced = feature_set.find_enum(enum.value)
    if referenced is None:
        pass
    elif referenced.parent_type is not None:
        # global value is a reference to a enum type value
        return '{}::{} as u32'.format(referenced.parent_type, enum.value)
    else:
        enum = referenced

    value = enum.value
    if value.endswith('"'):
        value = value[:-1] + r'\0"'
        return value

    if enum.value.startswith('EGL_CAST'):
        # EGL_CAST(type,value) -> value as type
        type_, value = enum.value.split('(', 1)[1].rsplit(')', 1)[0].split(',')
        return '{} as {}'.format(value, type_)

    for old, new in (('(', ''), (')', ''), ('f', ''),
                     ('U', ''), ('L', ''), ('~', '!')):
        value = value.replace(old, new)

    return value


def to_csharp_type(type_):
    parsed_type = type_ if isinstance(type_, ParsedType) else ParsedType.from_string(type_)

    if not parsed_type.is_pointer and parsed_type.type == 'void':
        return '()'

    type_ = _CSHARP_TYPE_MAPPING.get(parsed_type.type, parsed_type.type)

    prefix = ''
    suffix = ''
    if parsed_type.is_pointer > 0:
        if type_ == 'void':
            type_ = 'IntPtr'
        elif parsed_type.is_const:
            if type_ != 'IntPtr':
                suffix = '*'
        else:
            prefix = 'out '

    if parsed_type.is_array > 0:
        type_ = '[{};{}]'.format(type_, parsed_type.is_array)

    return ''.join(e for e in (prefix, type_, suffix)).strip()


def to_csharp_name(type_, name_):
    parsed_type = type_ if isinstance(type_, ParsedType) else ParsedType.from_string(type_)

    prefix = ''
    if parsed_type.is_pointer > 0:
        if parsed_type.type != 'void' and not parsed_type.is_const:
            prefix = 'out '

    return ''.join(e for e in (prefix, identifier(name_))).strip()


def to_csharp_params(command, mode='full'):
    if mode == 'names':
        return ', '.join(to_csharp_name(param.type, param.name) for param in command.params)
    elif mode == 'types':
        return ', '.join(to_csharp_type(param.type) for param in command.params)
    elif mode == 'full':
        return ', '.join(
            '{type} {name}'.format(type=to_csharp_type(param.type), name=identifier(param.name))
            for param in command.params
        )

    raise ValueError('invalid mode: ' + mode)


def identifier(name):
    return _CSHARP_KEYWORD_MAPPING.get(name, name)


class CSharpConfig(Config):
    ALIAS = ConfigOption(
        converter=bool,
        default=False,
        description='Automatically adds all extensions that ' +
                    'provide aliases for the current feature set.'
    )


class CSharpGenerator(JinjaGenerator):
    DISPLAY_NAME = 'C#'

    TEMPLATES = ['glad.generator.csharp']
    Config = CSharpConfig

    def __init__(self, *args, **kwargs):
        JinjaGenerator.__init__(self, *args, **kwargs)

        self.environment.filters.update(
            feature=lambda x: 'feature = "{}"'.format(x),
            enum_type=jinja2.contextfilter(lambda ctx, enum: enum_type(enum, ctx['feature_set'])),
            enum_value=jinja2.contextfilter(lambda ctx, enum: enum_value(enum, ctx['feature_set'])),
            type=to_csharp_type,
            params=to_csharp_params,
            identifier=identifier,
            no_prefix=jinja2.contextfilter(lambda ctx, value: strip_specification_prefix(value, ctx['spec']))
        )

    @property
    def id(self):
        return 'csharp'

    def select(self, spec, api, version, profile, extensions, config, sink=LoggingSink(__name__)):
        if extensions is not None:
            extensions = set(extensions)

            if config['ALIAS']:
                extensions.update(find_extensions_with_aliases(spec, api, version, profile, extensions))

        return JinjaGenerator.select(self, spec, api, version, profile, extensions, config, sink=sink)

    def get_template_arguments(self, spec, feature_set, config):
        args = JinjaGenerator.get_template_arguments(self, spec, feature_set, config)

        args.update(
            version=glad.__version__,
            aliases=collect_alias_information(feature_set.commands)
        )

        return args

    def get_templates(self, spec, feature_set, config):
        return [
            ('GL.cs', 'GL.cs')
        ]

