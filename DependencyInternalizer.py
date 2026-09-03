# -*- coding: utf-8 -*-
"""SBS Dependency Internalizer 1.7.0 — Designer 16 / PySide6.

Install this Python file through Designer's Plugin Manager > Browse.
Uses saved SBS XML; no Substance Automation Toolkit or third-party dependency.
Can also run from standard Python: python DependencyInternalizer.py --help
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

VERSION = '1.7.0'
_MENU = None
_DIALOG = None
_UI = None

UI_TEXT = {
    'title': ('SBS 依赖内部化', 'SBS Dependency Internalizer'),
    'language': ('语言', 'Language'),
    'hint': ('自动分析 A 的可编辑 SBS 依赖，将实际使用的函数 / Graph 递归复制进 A；'
             'SBSAR/SBSER 会迁移到输出旁并改为相对路径。\n'
             '处理磁盘上已保存的文件；请先在 Designer 中保存 A 及其依赖包。',
             'Automatically internalizes reachable functions and graphs from editable SBS dependencies. '
             'SBSAR/SBSER packages are copied beside the output and rewritten to relative paths.\n'
             'Files are read from disk; save A and all dependency packages in Designer first.'),
    'choose_a': ('选择 A…', 'Choose A…'),
    'current': ('当前图所在包', 'Current graph package'),
    'target_a': ('目标包 A', 'Target package A'),
    'choose_output': ('选择输出…', 'Choose output…'),
    'save_as': ('另存为', 'Save as'),
    'note': ('可定位的 B→C→D 等 SBS 引用会自动递归内部化；多个来源包彼此同名时仍会更名以避免误合并。',
             'Resolvable B→C→D SBS references are internalized recursively. Name collisions between different source packages are renamed to avoid accidental merging.'),
    'tree_dependency': ('依赖层级 / 资源', 'Dependency hierarchy / Resource'),
    'tree_result': ('处理结果', 'Result'),
    'analyze': ('1. 分析合并', '1. Analyze'),
    'generate': ('2. 生成 SBS', '2. Generate SBS'),
    'open': ('打开生成文件', 'Open generated file'),
    'final_output': ('最终输出', 'Final output'),
    'retained': ('保留的外部依赖', 'Retained external dependencies'),
    'items': ('%d 项', '%d items'),
    'migrate': ('生成时迁移并改为相对路径', 'Migrate and rewrite as relative path'),
    'keep': ('保留', 'Keep'),
    'merge_step': ('步骤 %d：并入 %s', 'Step %d: merge into %s'),
    'step_resources': ('本步并入资源', 'Resources merged in this step'),
    'rename': ('加 _from_*', 'Add _from_*'),
    'replace': ('覆盖同名资源', 'Replace same-name resource'),
    'keep_name': ('保持名称', 'Keep name'),
    'error': ('错误：', 'Error: '),
    'choose_a_title': ('选择目标 A.sbs', 'Choose target A.sbs'),
    'choose_output_title': ('选择新的输出文件名', 'Choose a new output filename'),
    'generated': ('已生成：', 'Generated: '),
    'open_requested': ('已请求 Designer 打开结果，请在 Explorer 中打开对应图检查。',
                       'Designer was asked to open the result. Open the corresponding graph in Explorer to verify it.'),
}


def ui_text(key, language='zh'):
    return UI_TEXT[key][1 if language == 'en' else 0]


_EN_REPLACEMENTS = (
    ('生成执行步骤：', 'Generation steps:'),
    ('未发现需内部化的可编辑 SBS；将迁移', 'No editable SBS needs internalization; compiled dependencies to migrate:'),
    ('个 SBSAR/SBSER 编译依赖。', ' SBSAR/SBSER package(s).'),
    ('原包内节点、参数、布局和连接保持不变。', 'Original nodes, parameters, layout, and connections are preserved.'),
    ('递归扫描包：', 'Packages recursively scanned: '),
    ('复制资源：', 'Resources copied: '),
    ('A 中重定向实例：', 'Instances redirected in A: '),
    ('合并顺序：', 'Merge order: '),
    ('原节点保留，参数、布局、连接不通过重建恢复。', 'Original nodes are preserved; parameters, layout, and connections are not reconstructed.'),
    ('重新分配冲突 UID：', 'Conflicting UIDs reassigned: '),
    ('继续保留的其他依赖：', 'Other retained dependencies:'),
    ('XML 连接检查通过：', 'XML connection checks passed: '),
    ('条；尚未进行 Designer 渲染验证。', '; Designer rendering has not yet been verified.'),
    (' 个；', '; '), (' 个。', '.'),
    ('（内存）', ' (in memory)'), ('处理', 'processed '), ('个资源。', ' resource(s).'),
    ('覆盖同名资源', 'replace same-name resource'), ('更名为 ', 'rename to '),
    ('映射为 ', 'map to '), ('保持名称', 'keep name'),
    ('迁移编译依赖 ', 'migrate compiled dependency '), ('SBS 引用改为 ', 'SBS reference rewritten to '),
    ('写出最终包 ', 'write final package '), ('步骤 ', 'Step '),
    ('错误：', 'Error: '), ('已生成：', 'Generated: '),
    ('请先分析合并。', 'Run Analyze first.'),
    ('输出文件必须使用 .sbs 扩展名。', 'The output file must use the .sbs extension.'),
    ('输出文件已存在，请换一个新文件名：', 'The output already exists; choose a new filename: '),
    ('分析后输入文件发生变化，请重新分析。', 'An input file changed after analysis; analyze again.'),
    ('依赖迁移目录已存在，为避免覆盖请换一个输出文件名：', 'The dependency migration folder already exists; choose a new output filename to avoid overwriting: '),
    ('请先保存当前包并打开其中的图，或用“选择 A”指定文件。', 'Save the current package and open one of its graphs, or choose A manually.'),
    ('文件已生成，但自动打开失败。请使用 File > Open 打开：', 'The file was generated, but could not be opened automatically. Use File > Open: '),
    ('无法识别实例引用格式：', 'Unrecognized instance reference format: '),
    ('包内资源路径重复：', 'Duplicate resource path in package: '),
    ('依赖 UID 缺失或重复。', 'A dependency UID is missing or duplicated.'),
    ('仅支持可编辑的 .sbs 文件，不支持 .sbsar。', 'Only editable .sbs files are supported as merge sources; .sbsar cannot be decompiled.'),
    ('不支持包含 DTD/ENTITY 声明的 SBS。', 'SBS files containing DTD/ENTITY declarations are not supported.'),
    ('读取 SBS 失败：', 'Failed to read SBS: '),
    ('文件不是支持的 SBS package XML。', 'The file is not a supported SBS package XML document.'),
    ('图中存在重复节点 UID。', 'The graph contains duplicate node UIDs.'),
    ('连接指向不存在的节点：', 'A connection points to a missing node: '),
    ('连接指向不存在的输出：', 'A connection points to a missing output: '),
    ('函数根节点不存在：', 'Function root node is missing: '),
    ('未知的同名资源处理方式：', 'Unknown name-collision policy: '),
    ('来源包和依赖 UID 必须同时提供，或都留空以自动分析。', 'Source package and dependency UID must both be provided, or both omitted for automatic analysis.'),
    ('A 中没有找到可内部化的 SBS，也没有可迁移的 SBSAR/SBSER 依赖。', 'No editable SBS or migratable SBSAR/SBSER dependency was found in A.'),
    ('A 中找不到所选依赖，请重新扫描。', 'The selected dependency was not found in A; scan again.'),
    ('不能将当前包自身作为外部依赖导入。', 'The current package cannot be imported as its own external dependency.'),
    ('A 与来源包不能是同一个文件。', 'A and the source package cannot be the same file.'),
    ('的 SBS 格式版本不同。请在同一 Designer 版本中分别保存后重试。', ' uses a different SBS format version. Save both files with the same Designer version and retry.'),
    ('可编辑依赖中没有可处理的函数／Graph 实例引用。', 'No supported function or Graph instance reference was found in the editable dependencies.'),
    ('待内部化的包还含位图／其他资源引用；此版本只合并函数和材质 Graph。', 'A package selected for internalization also contains bitmap or other resource references; this version merges only functions and material Graphs.'),
    ('中引用了缺失的依赖 ID：', ' references a missing dependency ID: '),
    ('中缺少被引用资源：', ' is missing referenced resource: '),
    ('暂不支持合并此类资源：', 'This resource type cannot currently be merged: '),
    ('资源内含外部媒体数据，暂不支持自动搬移：', 'The resource contains external media data, which cannot currently be moved automatically: '),
    ('资源中含未支持的引用字段：', 'The resource contains an unsupported reference field: '),
    ('A 中待内部化的包还含位图／其他资源引用；此版本只合并函数和材质 Graph。', 'A package selected for internalization in A also contains bitmap or other resource references; this version merges only functions and material Graphs.'),
    ('A 有多个自身依赖，请先在 Designer 中保存整理。', 'A has multiple self dependencies; clean up and save it in Designer first.'),
    ('无法定位待覆盖的同名资源。', 'Could not locate the same-name resource to replace.'),
    ('结果中实例的依赖 ID 不存在：', 'An instance in the result refers to a missing dependency ID: '),
    ('结果中内部引用无法解析：', 'An internal reference in the result cannot be resolved: '),
    ('函数实例的引用字段数量异常。', 'A function instance has an invalid number of reference fields.'),
    ('函数实例指向了非函数资源：', 'A function instance points to a non-function resource: '),
    ('函数输入接口不匹配：', 'Function input interface mismatch: '),
    ('Graph 实例指向了非 Graph 资源：', 'A Graph instance points to a non-Graph resource: '),
    ('Graph 输出接口不匹配：', 'Graph output interface mismatch: '),
    ('A 中含媒体资源，请将结果保存在 A 的同一文件夹，以保留媒体路径。', 'A contains media resources; save the result in the same folder as A to preserve media paths.'),
)


def localize_text(message, language='zh'):
    if language != 'en':
        return message
    result = str(message)
    # Longer phrases first prevents generic log words such as "处理" from
    # consuming part of a more specific error message.
    for source, target in sorted(_EN_REPLACEMENTS, key=lambda item: len(item[0]), reverse=True):
        result = result.replace(source, target)
    return result


class MergeError(Exception):
    """An unsupported or inconsistent file; no output should be written."""


def value(element, tag, default=''):
    child = element.find(tag)
    return child.get('v', default) if child is not None else default


def set_value(element, tag, val):
    child = element.find(tag)
    if child is None:
        child = ET.SubElement(element, tag)
    child.set('v', str(val))


def is_self(path):
    return path.replace('\\', '/').split('?')[-1] == 'himself'


def disk_path(raw, owner):
    """Resolve disk paths; leave Designer aliases to Designer itself."""
    if is_self(raw):
        return str(Path(owner).resolve())
    if re.match(r'^[A-Za-z][\w+.-]*://', raw) and not raw.startswith('file:'):
        return None
    if raw.startswith('file:'):
        u = urlsplit(raw)
        raw = unquote(u.path)
        if u.netloc:
            raw = '//' + u.netloc + raw
        if os.name == 'nt' and re.match(r'^/[A-Za-z]:', raw):
            raw = raw[1:]
    raw = raw.replace('\\', os.sep).replace('/', os.sep)
    if os.name != 'nt' and re.match(r'^[A-Za-z]:', raw):
        return None  # A Windows absolute path is not relative to a Linux cwd.
    p = Path(raw)
    return str((p if p.is_absolute() else Path(owner).parent / p).resolve())


def dependency_key(raw, owner):
    return os.path.normcase(disk_path(raw, owner) or raw)


def is_packaged_dependency(path):
    """Designer normally uses .sbsar; accept .sbser for existing pipelines too."""
    return Path(path).suffix.lower() in ('.sbsar', '.sbser')


def references(root):
    """Only known serialized resource-reference fields, never arbitrary text."""
    for element in root.iter('compInstance'):
        p = element.find('path')
        if p is not None:
            yield p
    for node in root.iter('paramNode'):
        if value(node, 'function') != 'instance':
            continue
        for data in node.findall('./funcDatas/funcData'):
            if value(data, 'name') == 'instance':
                p = data.find('./constantValue/constantValueString')
                if p is not None:
                    yield p


def parse_reference(element):
    raw = element.get('v', '')
    u = urlsplit(raw)
    deps = [v for k, v in parse_qsl(u.query) if k == 'dependency']
    if not raw.startswith('pkg:///') or len(deps) != 1:
        raise MergeError('无法识别实例引用格式：' + raw)
    return unquote(u.path).lstrip('/'), deps[0]


def rewrite_reference(element, path, dep):
    raw = element.get('v')
    old_path, old_dep = parse_reference(element)
    # Preserve extra query fields; package identifiers use Designer's raw path form.
    query = raw.split('?', 1)[1]
    query = re.sub(r'(^|&)dependency=[^&#]*', lambda m: m.group(1) + 'dependency=' + dep, query)
    element.set('v', 'pkg:///' + path + '?' + query)
    return element.get('v') != raw


def resource_index(root):
    result = {}
    def visit(content, prefix=''):
        if content is None:
            return
        for element in content:
            ident = value(element, 'identifier')
            if not ident:
                continue
            path = prefix + ident
            if path in result:
                raise MergeError('包内资源路径重复：' + path)
            result[path] = element
            if element.tag == 'group':
                visit(element.find('content'), path + '/')
    visit(root.find('content'))
    return result


def dependency_index(root):
    result = {}
    for dep in root.findall('./dependencies/dependency'):
        uid = value(dep, 'uid')
        if not uid or uid in result:
            raise MergeError('依赖 UID 缺失或重复。')
        result[uid] = dep
    return result


class Document:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        if Path(path).suffix.lower() != '.sbs':
            raise MergeError('仅支持可编辑的 .sbs 文件，不支持 .sbsar。')
        try:
            self.data = Path(path).read_bytes()
            # Never parse DTDs or entity declarations from an SBS file.
            if b'<!DOCTYPE' in self.data.upper() or b'<!ENTITY' in self.data.upper():
                raise MergeError('不支持包含 DTD/ENTITY 声明的 SBS。')
            self.root = ET.fromstring(self.data)
        except (OSError, ET.ParseError) as exc:
            raise MergeError('读取 SBS 失败：%s\n%s' % (path, exc)) from exc
        if self.root.tag != 'package' or self.root.find('content') is None:
            raise MergeError('文件不是支持的 SBS package XML。')
        self.sha256 = hashlib.sha256(self.data).hexdigest()
        self.resources = resource_index(self.root)
        self.deps = dependency_index(self.root)


def scan_dependencies(host_path):
    doc = Document(host_path)
    counts = Counter(parse_reference(p)[1] for p in references(doc.root))
    return [dict(uid=uid, filename=value(d, 'filename'), instances=counts[uid],
                 resolved_path=disk_path(value(d, 'filename'), doc.path))
            for uid, d in doc.deps.items() if not is_self(value(d, 'filename'))]


def _validate_local_links(root):
    """Validate node wiring without evaluating Designer's function engine."""
    checked = 0
    for container in root.iter():
        if container.tag not in ('paramNodes', 'compNodes'):
            continue
        nodes = [n for n in container if n.tag in ('paramNode', 'compNode')]
        by_uid = {value(n, 'uid'): n for n in nodes}
        if len(by_uid) != len(nodes):
            raise MergeError('图中存在重复节点 UID。')
        for node in nodes:
            for conn in node.findall('./connections/connection'):
                target = by_uid.get(value(conn, 'connRef'))
                if target is None:
                    raise MergeError('连接指向不存在的节点：' + value(conn, 'connRef'))
                out = value(conn, 'connRefOutput')
                if out and out not in {value(o, 'uid') for o in target.findall('./compOutputs/compOutput')}:
                    raise MergeError('连接指向不存在的输出：' + out)
                checked += 1
    for dyn in root.iter('dynamicValue'):
        nodes = dyn.find('paramNodes')
        rid = value(dyn, 'rootnode')
        if nodes is not None and rid and rid not in {value(n, 'uid') for n in nodes}:
            raise MergeError('函数根节点不存在：' + rid)
    return checked


class MergePlan:
    """Internalize the reachable resource closure of selected or all dependencies.

    Editable .sbs dependencies are followed transitively (including cycles).
    Built-in, aliased, missing, and non-.sbs packages remain dependencies.
    Source and host files are never overwritten.
    """
    def __init__(self, host_path, source_path=None, dependency_uid=None,
                 collision_policy='rename', collision_overrides=None):
        self.host = Document(host_path)
        if collision_policy not in ('rename', 'replace'):
            raise MergeError('未知的同名资源处理方式：' + str(collision_policy))
        self.collision_policy = collision_policy
        self.collision_overrides = set(collision_overrides or ())
        if (source_path is None) != (dependency_uid is None):
            raise MergeError('来源包和依赖 UID 必须同时提供，或都留空以自动分析。')
        if source_path is None:
            counts = Counter(parse_reference(p)[1] for p in references(self.host.root))
            root_sources = []
            seen_paths = {}
            host_key = dependency_key(self.host.path, self.host.path)
            for uid, item in self.host.deps.items():
                if not counts[uid] or is_self(value(item, 'filename')):
                    continue
                resolved = disk_path(value(item, 'filename'), self.host.path)
                if not resolved or not Path(resolved).is_file() or Path(resolved).suffix.lower() != '.sbs':
                    continue
                key = dependency_key(resolved, resolved)
                if key == host_key:
                    continue
                doc = seen_paths.get(key)
                if doc is None:
                    doc = Document(resolved)
                    seen_paths[key] = doc
                root_sources.append((uid, doc))
            if not root_sources:
                migratable = [disk_path(value(item, 'filename'), self.host.path)
                              for item in self.host.deps.values()
                              if not is_self(value(item, 'filename'))]
                migratable = [path for path in migratable
                              if path and is_packaged_dependency(path) and Path(path).is_file()]
                if not migratable:
                    raise MergeError('A 中没有找到可内部化的 SBS，也没有可迁移的 SBSAR/SBSER 依赖。')
        else:
            uid = str(dependency_uid)
            if uid not in self.host.deps:
                raise MergeError('A 中找不到所选依赖，请重新扫描。')
            if is_self(value(self.host.deps[uid], 'filename')):
                raise MergeError('不能将当前包自身作为外部依赖导入。')
            root_sources = [(uid, Document(source_path))]
        self.root_sources = root_sources
        self.selected, self.source = root_sources[0] if root_sources else (None, None)
        for _, doc in root_sources:
            if dependency_key(self.host.path, self.host.path) == dependency_key(doc.path, doc.path):
                raise MergeError('A 与来源包不能是同一个文件。')
            # Different serialization versions may have different UID semantics.
            if value(self.host.root, 'formatVersion') != value(doc.root, 'formatVersion'):
                raise MergeError('A 与 %s 的 SBS 格式版本不同。请在同一 Designer 版本中分别保存后重试。'
                                 % Path(doc.path).name)
        self.root = copy.deepcopy(self.host.root)
        self.log = []
        self.mapping = {}
        self.uid_map = {}
        self.copied = {}
        self.replaced = set()
        self.collision_candidates = set()
        self.external = []
        self.packaged_migrations = []
        self.rewritten = 0
        if root_sources:
            self._build()
        else:
            self._build_migration_only()

    def _build_migration_only(self):
        """Prepare an Export-with-dependencies result when A has no editable SBS input."""
        host = self.host
        host_key = dependency_key(host.path, host.path)
        deps = dependency_index(self.root)
        for uid, dep in deps.items():
            if is_self(value(dep, 'filename')):
                continue
            resolved = disk_path(value(host.deps[uid], 'filename'), host.path)
            if resolved:
                set_value(dep, 'filename', resolved.replace('\\', '/'))
        self.same_folder_only = any(e.tag in ('resource', 'source', 'sourceExternalCopy', 'sourceBinboon')
                                    for e in host.root.iter())
        set_value(self.root, 'fileUID', '{' + str(uuid.uuid4()) + '}')
        set_value(self.root, 'versionUID', '0')
        self._validate()
        self.host_key = host_key
        self.source_key = None
        self.documents = {}
        self.package_edges = {host_key: []}
        self.merge_steps = []
        self.stage_rows = {}
        self.retained_by_package = {
            host_key: sorted(value(dep, 'filename') for dep in deps.values()
                             if not is_self(value(dep, 'filename'))
                             and not value(dep, 'filename').startswith('sbs://'))
        }
        self.external = [value(dep, 'filename') for dep in deps.values()
                         if not is_self(value(dep, 'filename'))]
        count = sum(1 for path in self.external if is_packaged_dependency(path) and Path(path).is_file())
        self.log = ['未发现需内部化的可编辑 SBS；将迁移 %d 个 SBSAR/SBSER 编译依赖。' % count,
                    '原包内节点、参数、布局和连接保持不变。',
                    'XML 连接检查通过：%d 条；尚未进行 Designer 渲染验证。' % self.connections_checked]

    def _build(self):
        host, source = self.host, self.source
        host_key = dependency_key(host.path, host.path)
        a_refs = list(references(self.root))
        root_source_docs = {uid: doc for uid, doc in self.root_sources}
        direct = [p for p in a_refs if parse_reference(p)[1] in root_source_docs]
        if not direct:
            raise MergeError('可编辑依赖中没有可处理的函数／Graph 实例引用。')
        selected_refs = {id(p) for p in a_refs}
        for element in self.root.iter():
            raw = element.get('v', '')
            if raw.startswith('pkg:///') and id(element) not in selected_refs:
                _, dep = parse_reference(element)
                if dep in root_source_docs:
                    raise MergeError('待内部化的包还含位图／其他资源引用；此版本只合并函数和材质 Graph。')

        documents = {}
        self_deps = {}
        dependency_targets = {}

        def register_document(doc):
            key = dependency_key(doc.path, doc.path)
            existing = documents.get(key)
            if existing is not None:
                return key
            if value(host.root, 'formatVersion') != value(doc.root, 'formatVersion'):
                raise MergeError('A 与 %s 的 SBS 格式版本不同。请在同一 Designer 版本中分别保存后重试。'
                                 % Path(doc.path).name)
            documents[key] = doc
            self_deps[key] = {
                uid for uid, item in doc.deps.items()
                if is_self(value(item, 'filename'))
                or dependency_key(value(item, 'filename'), doc.path) == key
            }
            return key

        root_targets = {}
        for uid, doc in self.root_sources:
            root_targets[uid] = register_document(doc)
        source_key = root_targets[self.selected]

        def dependency_target(doc_key, dep_uid):
            token = (doc_key, dep_uid)
            if token in dependency_targets:
                return dependency_targets[token]
            doc = documents[doc_key]
            if dep_uid not in doc.deps:
                raise MergeError('%s 中引用了缺失的依赖 ID：%s'
                                 % (Path(doc.path).name, dep_uid))
            if dep_uid in self_deps[doc_key]:
                dependency_targets[token] = doc_key
                return doc_key
            item = doc.deps[dep_uid]
            filename = value(item, 'filename')
            key = dependency_key(filename, doc.path)
            if key == host_key:
                dependency_targets[token] = host_key
                return host_key
            resolved = disk_path(filename, doc.path)
            if resolved and Path(resolved).is_file() and Path(resolved).suffix.lower() == '.sbs':
                target_key = dependency_key(resolved, resolved)
                if target_key not in documents:
                    register_document(Document(resolved))
                dependency_targets[token] = target_key
                return target_key
            dependency_targets[token] = None
            return None

        needed = set()

        def collect(doc_key, path):
            token = (doc_key, path)
            if token in needed:
                return
            doc = documents[doc_key]
            resource = doc.resources.get(path)
            if resource is None:
                raise MergeError('%s 中缺少被引用资源：%s' % (Path(doc.path).name, path))
            if resource.tag not in ('function', 'graph'):
                raise MergeError('暂不支持合并此类资源：%s:%s (%s)'
                                 % (Path(doc.path).name, path, resource.tag))
            if any(x.tag in ('resource', 'source', 'sourceExternalCopy', 'sourceBinboon') for x in resource.iter()):
                raise MergeError('资源内含外部媒体数据，暂不支持自动搬移：%s:%s'
                                 % (Path(doc.path).name, path))
            known = {id(p) for p in references(resource)}
            for x in resource.iter():
                if x.get('v', '').startswith('pkg:///') and id(x) not in known:
                    raise MergeError('资源中含未支持的引用字段：%s:%s'
                                     % (Path(doc.path).name, path))
            # Add before descending so B -> C -> D -> C cycles terminate.
            needed.add(token)
            for p in references(resource):
                other, dep = parse_reference(p)
                target = dependency_target(doc_key, dep)
                if target is not None and target != host_key:
                    collect(target, other)

        for p in direct:
            path, dep = parse_reference(p)
            collect(root_targets[dep], path)

        # A may already reference a package (for example C) that is also reached
        # through the selected B package. Fold every such A dependency into this
        # same import, otherwise the copied C resources and A's old C references
        # diverge and C remains unnecessarily external.
        host_import_targets = dict(root_targets)
        while True:
            before = (len(documents), len(host_import_targets), len(needed))
            for uid, item in host.deps.items():
                if uid in host_import_targets or is_self(value(item, 'filename')):
                    continue
                target_key = dependency_key(value(item, 'filename'), host.path)
                if target_key in documents:
                    host_import_targets[uid] = target_key
            for p in a_refs:
                path, dep = parse_reference(p)
                target_key = host_import_targets.get(dep)
                if target_key is not None:
                    collect(target_key, path)
            after = (len(documents), len(host_import_targets), len(needed))
            if after == before:
                break

        known_host_refs = {id(p) for p in a_refs}
        for element in self.root.iter():
            raw = element.get('v', '')
            if raw.startswith('pkg:///') and id(element) not in known_host_refs:
                _, dep = parse_reference(element)
                if dep in host_import_targets:
                    raise MergeError('A 中待内部化的包还含位图／其他资源引用；此版本只合并函数和材质 Graph。')

        # Build the package graph from references that are actually reachable.
        # A package directly referenced by A can still be placed below another
        # imported package (A -> B -> C and A -> C becomes D -> C -> B -> A).
        package_graph = {host_key: set(host_import_targets.values())}
        for doc_key, path in needed:
            package_graph.setdefault(doc_key, set())
            for ref in references(documents[doc_key].resources[path]):
                _, dep = parse_reference(ref)
                target = dependency_target(doc_key, dep)
                if target is not None and target != doc_key:
                    package_graph[doc_key].add(target)

        merge_children = {host_key: []}
        visited_packages = {host_key}

        def assign_merge_tree(parent):
            children = sorted(package_graph.get(parent, ()),
                              key=lambda key: (key != source_key, key))
            for child in children:
                if child == host_key or child in visited_packages:
                    continue
                visited_packages.add(child)
                merge_children.setdefault(parent, []).append(child)
                merge_children.setdefault(child, [])
                assign_merge_tree(child)

        assign_merge_tree(host_key)
        for key in sorted(documents):
            if key not in visited_packages:
                visited_packages.add(key)
                merge_children[host_key].append(key)
                merge_children.setdefault(key, [])
                assign_merge_tree(key)

        aliases = {}
        stage_rows = {}
        stage_candidates = set()
        stage_replaced = set()

        def resolved_origin(origin):
            trail = []
            while origin in aliases:
                trail.append(origin)
                origin = aliases[origin]
            for item in trail:
                aliases[item] = origin
            return origin

        def staged_unique_path(path, occupied, origin):
            doc_key, _ = origin
            owner = host if doc_key == host_key else documents[doc_key]
            suffix = re.sub(r'[^A-Za-z0-9_]', '_', Path(owner.path).stem) or 'source'
            base = path + '_from_' + suffix
            result = base
            count = 2
            while result in occupied:
                result = base + '_' + str(count)
                count += 1
            return result

        needed_by_doc = {}
        for token in needed:
            needed_by_doc.setdefault(token[0], []).append(token)

        def build_bundle(parent_key):
            owner = host if parent_key == host_key else documents[parent_key]
            if parent_key == host_key:
                bundle = {(host_key, path): path for path, resource in host.resources.items()
                          if resource.tag in ('function', 'graph')}
            else:
                bundle = {token: token[1] for token in needed_by_doc.get(parent_key, ())}
            occupied = {path: None for path, resource in owner.resources.items()
                        if resource.tag in ('function', 'graph')}
            for origin, path in bundle.items():
                occupied[path] = origin
            for child_key in merge_children.get(parent_key, ()):
                child_bundle = build_bundle(child_key)
                rows = []
                for origin, incoming_path in sorted(child_bundle.items(), key=lambda item: (item[1], item[0])):
                    output_path = incoming_path
                    conflict = incoming_path in occupied
                    choice_key = (parent_key, child_key, origin[0], origin[1])
                    replace = False
                    if conflict:
                        stage_candidates.add(choice_key)
                        replace = (self.collision_policy == 'replace'
                                   or choice_key in self.collision_overrides)
                        if replace:
                            previous = occupied[incoming_path]
                            if previous is not None and previous != origin:
                                aliases[previous] = origin
                                bundle.pop(previous, None)
                            stage_replaced.add(choice_key)
                        else:
                            output_path = staged_unique_path(incoming_path, occupied, origin)
                    bundle[origin] = output_path
                    occupied[output_path] = origin
                    rows.append((origin, incoming_path, output_path, conflict, choice_key, replace))
                stage_rows[(parent_key, child_key)] = rows
            return bundle

        final_bundle = build_bundle(host_key)
        surviving_imports = {origin for origin in final_bundle if origin[0] != host_key}
        removed_host_origins = {
            origin for origin in aliases
            if origin[0] == host_key and resolved_origin(origin) != origin
        }
        planned_mapping = {
            token: final_bundle[resolved_origin(token)] for token in needed
        }

        self.merge_children = merge_children
        self.stage_rows = stage_rows
        self.merge_steps = list(stage_rows)
        self.collision_candidates = stage_candidates
        self.replaced = stage_replaced

        self.documents = documents

        used = {e.get('v') for e in self.root.iter('uid')}
        # Reserve every reachable package UID, so allocations cannot steal IDs
        # that a later imported package could otherwise preserve.
        reserved = set(used)
        for doc in documents.values():
            reserved.update(e.get('v') for e in doc.root.iter('uid'))
        next_uid = max([int(x) for x in reserved if x and x.isdigit()] + [1000000000]) + 1

        def new_uid():
            nonlocal next_uid
            while str(next_uid) in reserved:
                next_uid += 1
            if next_uid >= 4294967295:
                next_uid = 1000000000
                while str(next_uid) in reserved:
                    next_uid += 1
            result = str(next_uid)
            reserved.add(result)
            used.add(result)
            next_uid += 1
            return result

        uid_maps = {}

        def imported_uid(doc_key, old):
            mapping = uid_maps.setdefault(doc_key, {})
            if old not in mapping:
                mapping[old] = new_uid() if old in used else old
                used.add(mapping[old])
                if doc_key == source_key:
                    self.uid_map[old] = mapping[old]
            return mapping[old]

        deps = self.root.find('dependencies')
        a_deps = dependency_index(self.root)
        selves = [uid for uid, d in a_deps.items() if is_self(value(d, 'filename'))]
        if len(selves) > 1:
            raise MergeError('A 有多个自身依赖，请先在 Designer 中保存整理。')
        if selves:
            self.self_uid = selves[0]
        else:
            self.self_uid = self.selected
            set_value(a_deps[self.selected], 'filename', '?himself')
            set_value(a_deps[self.selected], 'fileUID', '0')
            set_value(a_deps[self.selected], 'versionUID', '0')
        for uid in host_import_targets:
            if uid == self.self_uid:
                continue
            item = a_deps.get(uid)
            if item is not None:
                deps.remove(item)
                del a_deps[uid]
        dep_map = {}

        def retain_dependency(doc_key, dep):
            token = (doc_key, dep)
            if token in dep_map:
                return dep_map[token]
            target = dependency_target(doc_key, dep)
            if target is not None:
                dep_map[token] = self.self_uid
                return self.self_uid
            doc = documents[doc_key]
            item = doc.deps[dep]
            filename = value(item, 'filename')
            key = dependency_key(filename, doc.path)
            matching = next((uid for uid, existing in a_deps.items()
                             if dependency_key(value(existing, 'filename'), host.path) == key), None)
            if matching is None:
                matching = new_uid() if dep in used else dep
                used.add(matching)
                cloned = copy.deepcopy(item)
                set_value(cloned, 'uid', matching)
                resolved = disk_path(filename, doc.path)
                set_value(cloned, 'filename', resolved.replace('\\', '/') if resolved else filename)
                deps.append(cloned)
                a_deps[matching] = cloned
            dep_map[token] = matching
            return matching

        for doc_key, path in sorted(needed):
            doc = documents[doc_key]
            for p in references(doc.resources[path]):
                _, dep = parse_reference(p)
                retain_dependency(doc_key, dep)

        dest_index = resource_index(self.root)
        dest_content = self.root.find('content')
        group_map = {}

        def remove_element(target):
            for parent in self.root.iter():
                if target in list(parent):
                    parent.remove(target)
                    return
            raise MergeError('无法定位待覆盖的同名资源。')

        for _, path in sorted(removed_host_origins):
            existing = dest_index.get(path)
            if existing is not None and existing.tag in ('function', 'graph'):
                remove_element(existing)
                del dest_index[path]

        def unique_path(path, doc):
            if path not in dest_index:
                return path
            suffix = re.sub(r'[^A-Za-z0-9_]', '_', Path(doc.path).stem) or 'source'
            base = path + '_from_' + suffix
            result = base
            count = 2
            while result in dest_index:
                result = base + '_' + str(count)
                count += 1
            return result

        def ensure_groups(doc_key, parts):
            doc = documents[doc_key]
            content = dest_content
            old_prefix = ''
            new_prefix = ''
            for name in parts:
                old_prefix = (old_prefix + '/' + name).strip('/')
                group_token = (doc_key, old_prefix)
                if group_token in group_map:
                    new_prefix, element = group_map[group_token]
                    content = element.find('content')
                    continue
                candidate = (new_prefix + '/' + name).strip('/')
                existing = dest_index.get(candidate)
                if existing is not None and existing.tag == 'group':
                    element = existing
                else:
                    actual = unique_path(candidate, doc)
                    template = doc.resources.get(old_prefix)
                    element = ET.Element('group')
                    if template is not None and template.tag == 'group':
                        for child in template:
                            if child.tag != 'content':
                                element.append(copy.deepcopy(child))
                    old_uid = value(element, 'uid')
                    set_value(element, 'uid', imported_uid(doc_key, old_uid) if old_uid else new_uid())
                    set_value(element, 'identifier', actual.rsplit('/', 1)[-1])
                    ET.SubElement(element, 'content')
                    content.append(element)
                    candidate = actual
                    dest_index[candidate] = element
                new_prefix = candidate
                group_map[group_token] = (candidate, element)
                content = element.find('content')
            return new_prefix, content

        resource_mapping = {}
        copied_by_origin = {}
        actual_survivor_paths = {}
        ordered_needed = sorted(surviving_imports,
                                key=lambda item: (item[0] != source_key, item[0], item[1]))
        for doc_key, path in ordered_needed:
            doc = documents[doc_key]
            token = (doc_key, path)
            parts = path.split('/')
            prefix, content = ensure_groups(doc_key, parts[:-1])
            planned_path = final_bundle[token]
            planned_leaf = planned_path.rsplit('/', 1)[-1]
            candidate = (prefix + '/' + planned_leaf).strip('/')
            source_resource = doc.resources[path]
            target_path = unique_path(candidate, doc)
            cloned = copy.deepcopy(source_resource)
            set_value(cloned, 'identifier', target_path.rsplit('/', 1)[-1])
            content.append(cloned)
            dest_index[target_path] = cloned
            actual_survivor_paths[token] = target_path
            copied_by_origin[token] = cloned
            label = path if doc_key == source_key else Path(doc.path).name + ':' + path
            self.copied[label] = cloned
            for e in cloned.iter('uid'):
                imported_uid(doc_key, e.get('v'))

        for token in needed:
            resource_mapping[token] = actual_survivor_paths[resolved_origin(token)]
            if token[0] == source_key:
                self.mapping[token[1]] = resource_mapping[token]

        self.resource_mapping = resource_mapping

        # UID fields are structural only; numeric constants must never be rewritten.
        uid_fields = {'uid', 'connRef', 'connRefOutput', 'rootnode', 'output', 'entry', 'parent'}
        for (doc_key, old_path), cloned in copied_by_origin.items():
            mapping = uid_maps[doc_key]
            for e in cloned.iter():
                if e.tag in uid_fields and e.get('v') in mapping:
                    e.set('v', mapping[e.get('v')])
            for p in references(cloned):
                path, dep = parse_reference(p)
                target_doc = dependency_target(doc_key, dep)
                if target_doc == host_key:
                    target_path = path
                    target_dep = self.self_uid
                elif target_doc is not None:
                    target_path = resource_mapping[(target_doc, path)]
                    target_dep = self.self_uid
                else:
                    target_path = path
                    target_dep = dep_map[(doc_key, dep)]
                self.rewritten += rewrite_reference(p, target_path, target_dep)
        for p in a_refs:
            path, dep = parse_reference(p)
            target_doc = host_import_targets.get(dep)
            if target_doc is not None:
                self.rewritten += rewrite_reference(
                    p, resource_mapping[(target_doc, path)], self.self_uid)

        # Rebase retained A dependencies when exporting to another folder.
        for dep in deps:
            if value(dep, 'uid') in host.deps and not is_self(value(dep, 'filename')):
                raw = value(host.deps[value(dep, 'uid')], 'filename')
                resolved = disk_path(raw, host.path)
                if resolved:
                    set_value(dep, 'filename', resolved.replace('\\', '/'))
        # Direct media paths in A may be relative; changing the output folder is
        # disallowed in that case, rather than silently changing media resolution.
        self.same_folder_only = any(e.tag in ('resource', 'source', 'sourceExternalCopy', 'sourceBinboon')
                                    for e in host.root.iter())
        # Give the new package its own file identity when A stays open in Designer.
        set_value(self.root, 'fileUID', '{' + str(uuid.uuid4()) + '}')
        set_value(self.root, 'versionUID', '0')
        self._validate()
        self.external = [value(d, 'filename') for d in deps if not is_self(value(d, 'filename'))]
        visible_external = [path for path in self.external if not path.startswith('sbs://')]
        retained_by_package = {host_key: set(visible_external)}
        for (doc_key, path), resource in ((token, documents[token[0]].resources[token[1]])
                                          for token in needed):
            retained_by_package.setdefault(doc_key, set())
            for ref in references(resource):
                _, dep = parse_reference(ref)
                target = dependency_target(doc_key, dep)
                if target is None:
                    filename = value(documents[doc_key].deps[dep], 'filename')
                    if not filename.startswith('sbs://'):
                        retained_by_package[doc_key].add(filename)
        self.host_key = host_key
        self.source_key = source_key
        self.package_edges = {key: list(children) for key, children in merge_children.items()}
        self.retained_by_package = {
            key: sorted(paths) for key, paths in retained_by_package.items() if paths
        }
        self.log = ['递归扫描包：%d 个；复制资源：%d 个；A 中重定向实例：%d 个。'
                    % (len(documents), len(copied_by_origin),
                       sum(1 for p in a_refs if parse_reference(p)[1] in host_import_targets)),
                    '合并顺序：' + '；'.join(
                        '%s → %s' % (
                            Path(documents[child].path).name,
                            Path(host.path).name if parent == host_key else Path(documents[parent].path).name)
                        for parent, child in self.merge_steps),
                    '原节点保留，参数、布局、连接不通过重建恢复。',
                    '重新分配冲突 UID：%d 个。'
                    % sum(old != new for mapping in uid_maps.values() for old, new in mapping.items())]
        for (doc_key, old), new in resource_mapping.items():
            self.log.append('  %s:%s  →  %s' % (Path(documents[doc_key].path).name, old, new))
        if visible_external:
            self.log.append('继续保留的其他依赖：')
            self.log.extend('  ' + x for x in visible_external)
        self.log.append('XML 连接检查通过：%d 条；尚未进行 Designer 渲染验证。' % self.connections_checked)

    def generation_log(self, output_path):
        def package_name(key):
            if key == self.host_key:
                return Path(self.host.path).name
            return Path(self.documents[key].path).name

        lines = ['生成执行步骤：']
        for index, (parent, child) in enumerate(self.merge_steps, 1):
            rows = self.stage_rows.get((parent, child), [])
            lines.append('步骤 %d（内存）：%s → %s；处理 %d 个资源。'
                         % (index, package_name(child), package_name(parent), len(rows)))
            for origin, incoming, output, conflict, _, replaced in rows:
                origin_name = package_name(origin[0])
                label = origin[1] if origin[0] == child else origin_name + ':' + origin[1]
                if conflict and replaced:
                    action = '覆盖同名资源'
                elif conflict:
                    action = '更名为 ' + output
                elif incoming != output:
                    action = '映射为 ' + output
                else:
                    action = '保持名称'
                lines.append('  %s：%s' % (label, action))
        step = len(self.merge_steps) + 1
        for source, destination, relative in self.packaged_migrations:
            lines.append('步骤 %d：迁移编译依赖 %s → %s；SBS 引用改为 %s'
                         % (step, source, destination, relative))
            step += 1
        lines.append('步骤 %d：写出最终包 %s' % (step, str(output_path)))
        return lines

    def _validate(self):
        deps = dependency_index(self.root)
        index = resource_index(self.root)
        for ref in references(self.root):
            path, dep = parse_reference(ref)
            if dep not in deps:
                raise MergeError('结果中实例的依赖 ID 不存在：' + dep)
            if is_self(value(deps[dep], 'filename')) and path not in index:
                raise MergeError('结果中内部引用无法解析：' + path)
        for n in self.root.iter('paramNode'):
            if value(n, 'function') != 'instance':
                continue
            refs = list(references(n))
            if len(refs) != 1:
                raise MergeError('函数实例的引用字段数量异常。')
            path, dep = parse_reference(refs[0])
            if not is_self(value(deps[dep], 'filename')):
                continue
            target = index[path]
            if target.tag != 'function':
                raise MergeError('函数实例指向了非函数资源：' + path)
            names = {value(p, 'identifier') for p in target.findall('./paraminputs/paraminput')}
            if any(value(c, 'identifier') not in names for c in n.findall('./connections/connection')):
                raise MergeError('函数输入接口不匹配：' + path)
        for comp in self.root.iter('compInstance'):
            path, dep = parse_reference(comp.find('path'))
            if not is_self(value(deps[dep], 'filename')):
                continue
            target = index[path]
            if target.tag != 'graph':
                raise MergeError('Graph 实例指向了非 Graph 资源：' + path)
            names = {value(p, 'identifier') for p in target.findall('./graphOutputs/graphoutput')}
            for bridge in comp.findall('./outputBridgings/outputBridging'):
                if value(bridge, 'identifier') not in names:
                    raise MergeError('Graph 输出接口不匹配：' + path)
        self.connections_checked = _validate_local_links(self.root)

    def save(self, output_path):
        out = Path(output_path).resolve()
        if out.suffix.lower() != '.sbs':
            raise MergeError('输出文件必须使用 .sbs 扩展名。')
        if out.exists():
            raise MergeError('输出文件已存在，请换一个新文件名：' + str(out))
        if self.same_folder_only and out.parent != Path(self.host.path).parent:
            raise MergeError('A 中含媒体资源，请将结果保存在 A 的同一文件夹，以保留媒体路径。')
        for doc in [self.host] + list(self.documents.values()):
            if hashlib.sha256(Path(doc.path).read_bytes()).hexdigest() != doc.sha256:
                raise MergeError('分析后输入文件发生变化，请重新分析。')
        # Compiled packages cannot be internalized, but can travel beside the
        # generated SBS in the same way as Designer's Export with dependencies.
        output_root = copy.deepcopy(self.root)
        packaged = {}
        packaged_deps = []
        for dep in output_root.findall('./dependencies/dependency'):
            raw = value(dep, 'filename')
            resolved = disk_path(raw, self.host.path)
            if not resolved or not is_packaged_dependency(resolved):
                continue
            source = Path(resolved)
            if not source.is_file():
                continue
            key = os.path.normcase(str(source.resolve()))
            packaged.setdefault(key, source.resolve())
            packaged_deps.append((dep, key))

        migration_dir = out.with_name(out.stem + '_dependencies')
        if packaged and migration_dir.exists():
            raise MergeError('依赖迁移目录已存在，为避免覆盖请换一个输出文件名：' + str(migration_dir))

        names = {}
        occupied = set()
        for key, source in sorted(packaged.items(), key=lambda item: item[0]):
            candidate = source.name
            index = 2
            while candidate.lower() in occupied:
                candidate = '%s_%d%s' % (source.stem, index, source.suffix)
                index += 1
            occupied.add(candidate.lower())
            names[key] = candidate
        for dep, key in packaged_deps:
            relative = os.path.relpath(migration_dir / names[key], out.parent).replace('\\', '/')
            set_value(dep, 'filename', relative)

        data = ET.tostring(output_root, encoding='UTF-8', xml_declaration=True)
        ET.fromstring(data)
        # Exclusive create avoids overwriting any source or existing result.
        created_dir = False
        copied = []
        try:
            if packaged:
                migration_dir.mkdir(parents=False, exist_ok=False)
                created_dir = True
                for key, source in sorted(packaged.items(), key=lambda item: item[0]):
                    destination = migration_dir / names[key]
                    shutil.copy2(source, destination)
                    copied.append(destination)
            with out.open('xb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            # If opening succeeded but writing failed, remove only this new file.
            if 'f' in locals():
                out.unlink(missing_ok=True)
            for destination in reversed(copied):
                destination.unlink(missing_ok=True)
            if created_dir:
                try:
                    migration_dir.rmdir()
                except OSError:
                    pass
            raise
        self.packaged_migrations = []
        for key, source in sorted(packaged.items(), key=lambda item: item[0]):
            destination = migration_dir / names[key]
            relative = os.path.relpath(destination, out.parent).replace('\\', '/')
            self.packaged_migrations.append((str(source), str(destination), relative))
        return str(out)


def _show_dialog():
    global _DIALOG
    from PySide6 import QtCore, QtWidgets
    import sd
    if _DIALOG is not None:
        _DIALOG.show()
        _DIALOG.raise_()
        _DIALOG.activateWindow()
        return
    app = sd.getContext().getSDApplication()
    ui = app.getQtForPythonUIMgr()

    class InternalizerDialog(QtWidgets.QDialog):
        def __init__(self):
            super().__init__(ui.getMainWindow())
            self.settings = QtCore.QSettings('Xiaofeng', 'SBSDependencyInternalizer')
            self.language = self.settings.value('language', 'zh')
            if self.language not in ('zh', 'en'):
                self.language = 'zh'
            self.resize(920, 760)
            self.plan = None
            self.collision_overrides = set()
            layout = QtWidgets.QVBoxLayout(self)
            language_row = QtWidgets.QHBoxLayout()
            language_row.addStretch(1)
            self.language_label = QtWidgets.QLabel()
            language_row.addWidget(self.language_label)
            self.language_combo = QtWidgets.QComboBox()
            self.language_combo.addItem('中文', 'zh')
            self.language_combo.addItem('English', 'en')
            self.language_combo.setCurrentIndex(1 if self.language == 'en' else 0)
            self.language_combo.currentIndexChanged.connect(self.change_language)
            language_row.addWidget(self.language_combo)
            layout.addLayout(language_row)
            self.hint = QtWidgets.QLabel(); self.hint.setWordWrap(True)
            layout.addWidget(self.hint)
            form = QtWidgets.QFormLayout()
            layout.addLayout(form)
            self.host_edit = QtWidgets.QLineEdit()
            row = QtWidgets.QWidget(); h = QtWidgets.QHBoxLayout(row); h.setContentsMargins(0,0,0,0)
            h.addWidget(self.host_edit)
            self.host_browse = QtWidgets.QPushButton(); self.host_browse.clicked.connect(self.choose_host); h.addWidget(self.host_browse)
            self.current_btn = QtWidgets.QPushButton(); self.current_btn.clicked.connect(self.use_current); h.addWidget(self.current_btn)
            self.host_label = QtWidgets.QLabel(); form.addRow(self.host_label, row)
            self.output_edit = QtWidgets.QLineEdit()
            row = QtWidgets.QWidget(); h = QtWidgets.QHBoxLayout(row); h.setContentsMargins(0,0,0,0)
            h.addWidget(self.output_edit)
            self.output_browse = QtWidgets.QPushButton(); self.output_browse.clicked.connect(self.choose_output); h.addWidget(self.output_browse)
            self.output_label = QtWidgets.QLabel(); form.addRow(self.output_label, row)
            self.note = QtWidgets.QLabel(); self.note.setWordWrap(True); layout.addWidget(self.note)
            result_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
            self.tree = QtWidgets.QTreeWidget()
            self.tree.setColumnCount(2)
            self.tree.setHeaderLabels(['', ''])
            self.tree.setAlternatingRowColors(True)
            self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
            self.tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            result_splitter.addWidget(self.tree)
            self.log = QtWidgets.QPlainTextEdit(); self.log.setReadOnly(True)
            result_splitter.addWidget(self.log)
            result_splitter.setStretchFactor(0, 3)
            result_splitter.setStretchFactor(1, 2)
            layout.addWidget(result_splitter, 1)
            row = QtWidgets.QHBoxLayout(); layout.addLayout(row)
            self.analyze_btn = QtWidgets.QPushButton(); self.analyze_btn.clicked.connect(self.analyze)
            row.addWidget(self.analyze_btn)
            self.save_btn = QtWidgets.QPushButton(); self.save_btn.setEnabled(False); self.save_btn.clicked.connect(self.generate)
            row.addWidget(self.save_btn)
            self.open_btn = QtWidgets.QPushButton(); self.open_btn.setEnabled(False); self.open_btn.clicked.connect(self.open_output)
            row.addWidget(self.open_btn)
            self.host_edit.textChanged.connect(self.invalidate)
            self.output_edit.textChanged.connect(lambda *_: self.open_btn.setEnabled(False))
            self.host_edit.textChanged.connect(self.host_changed)
            self.result_path = None
            self.retranslate_ui()
            self.use_current(quiet=True)

        def t(self, key):
            return ui_text(key, self.language)

        def change_language(self, *_):
            self.language = self.language_combo.currentData()
            self.settings.setValue('language', self.language)
            self.retranslate_ui()
            self.show_dependency_tree()
            self.refresh_log()

        def retranslate_ui(self):
            self.setWindowTitle(self.t('title') + '  ' + VERSION)
            self.language_label.setText(self.t('language'))
            self.hint.setText(self.t('hint'))
            self.host_browse.setText(self.t('choose_a'))
            self.current_btn.setText(self.t('current'))
            self.host_label.setText(self.t('target_a'))
            self.output_browse.setText(self.t('choose_output'))
            self.output_label.setText(self.t('save_as'))
            self.note.setText(self.t('note'))
            self.tree.setHeaderLabels([self.t('tree_dependency'), self.t('tree_result')])
            self.analyze_btn.setText(self.t('analyze'))
            self.save_btn.setText(self.t('generate'))
            self.open_btn.setText(self.t('open'))

        def refresh_log(self):
            if self.plan is None:
                return
            lines = [localize_text(line, self.language) for line in self.plan.log]
            if self.result_path:
                lines.append('')
                lines.extend(localize_text(line, self.language)
                             for line in self.plan.generation_log(self.result_path))
                lines.append(self.t('generated') + self.result_path)
            self.log.setPlainText('\n'.join(lines))

        def error(self, exc):
            message = localize_text(str(exc), self.language)
            self.log.appendPlainText(self.t('error') + message)
            QtWidgets.QMessageBox.warning(self, self.t('title'), message)

        def invalidate(self, *_):
            self.collision_overrides.clear()
            self.plan = None
            self.save_btn.setEnabled(False)
            self.open_btn.setEnabled(False)
            self.tree.clear()

        def show_dependency_tree(self):
            self.tree.clear()
            if self.plan is None:
                return
            plan = self.plan
            root = QtWidgets.QTreeWidgetItem(
                self.tree, [Path(plan.host.path).name, self.t('final_output')])
            step_numbers = {edge: index + 1 for index, edge in enumerate(plan.merge_steps)}

            def add_retained(parent, key):
                paths = plan.retained_by_package.get(key, [])
                if not paths:
                    return
                group = QtWidgets.QTreeWidgetItem(parent, [self.t('retained'), self.t('items') % len(paths)])
                for path in paths:
                    owner = plan.host if key == plan.host_key else plan.documents[key]
                    resolved = disk_path(path, owner.path)
                    action = (self.t('migrate')
                              if resolved and is_packaged_dependency(resolved) and Path(resolved).is_file()
                              else self.t('keep'))
                    QtWidgets.QTreeWidgetItem(group, [path, action])

            def add_package(parent, parent_key, key):
                doc = plan.documents[key]
                parent_name = (Path(plan.host.path).name if parent_key == plan.host_key
                               else Path(plan.documents[parent_key].path).name)
                step = step_numbers[(parent_key, key)]
                item = QtWidgets.QTreeWidgetItem(
                    parent, [Path(doc.path).name,
                             self.t('merge_step') % (step, parent_name)])
                rows = plan.stage_rows.get((parent_key, key), [])
                if rows:
                    group = QtWidgets.QTreeWidgetItem(item, [self.t('step_resources'), self.t('items') % len(rows)])
                    for origin, incoming, output, conflict, choice_key, replaced in rows:
                        origin_doc = plan.documents[origin[0]]
                        label = origin[1] if origin[0] == key else Path(origin_doc.path).name + ':' + origin[1]
                        row = QtWidgets.QTreeWidgetItem(group, [label, ''])
                        if conflict:
                            choice = QtWidgets.QComboBox(self.tree)
                            rename_label = self.t('rename') + (('  →  ' + output) if output != incoming else '')
                            choice.addItem(rename_label, False)
                            choice.addItem(self.t('replace'), True)
                            choice.setCurrentIndex(1 if replaced else 0)
                            choice.currentIndexChanged.connect(
                                lambda index, token=choice_key: self.set_collision_choice(token, index))
                            self.tree.setItemWidget(row, 1, choice)
                        else:
                            result = self.t('keep_name') if incoming == output else '→ ' + output
                            row.setText(1, result)
                add_retained(item, key)
                for child in plan.package_edges.get(key, []):
                    add_package(item, key, child)

            for child in plan.package_edges.get(plan.host_key, []):
                add_package(root, plan.host_key, child)
            add_retained(root, plan.host_key)
            self.tree.expandAll()
            self.tree.resizeColumnToContents(1)

        def set_collision_choice(self, token, index):
            if index == 1:
                self.collision_overrides.add(token)
            else:
                self.collision_overrides.discard(token)
            QtCore.QTimer.singleShot(0, self.run_analysis)

        def host_changed(self, *_):
            raw = self.host_edit.text().strip()
            if not raw:
                return
            path = Path(raw)
            if path.suffix.lower() != '.sbs':
                return
            output = path.with_name(path.stem + '_internalized.sbs')
            count = 2
            while output.exists():
                output = path.with_name(path.stem + '_internalized_' + str(count) + '.sbs')
                count += 1
            self.output_edit.setText(str(output))

        def choose_host(self):
            p, _ = QtWidgets.QFileDialog.getOpenFileName(self, self.t('choose_a_title'), '', 'Substance (*.sbs)')
            if p:
                self.host_edit.setText(p)

        def choose_output(self):
            p, _ = QtWidgets.QFileDialog.getSaveFileName(self, self.t('choose_output_title'), self.output_edit.text(), 'Substance (*.sbs)')
            if p:
                self.output_edit.setText(p if p.lower().endswith('.sbs') else p + '.sbs')

        def use_current(self, *_, quiet=False):
            try:
                graph = ui.getCurrentGraph()
                package = graph.getPackage() if graph is not None else None
                path = package.getFilePath() if package is not None else None
                if not path:
                    if quiet:
                        return
                    raise MergeError('请先保存当前包并打开其中的图，或用“选择 A”指定文件。')
                self.host_edit.setText(path)
            except Exception as exc:
                if not quiet:
                    self.error(exc)

        def analyze(self, *_):
            self.collision_overrides.clear()
            self.run_analysis()

        def run_analysis(self):
            self.plan = None
            self.save_btn.setEnabled(False)
            self.open_btn.setEnabled(False)
            self.tree.clear()
            try:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
                try:
                    self.plan = MergePlan(
                        self.host_edit.text().strip(),
                        collision_overrides=self.collision_overrides)
                finally:
                    QtWidgets.QApplication.restoreOverrideCursor()
                self.show_dependency_tree()
                self.refresh_log()
                self.save_btn.setEnabled(True)
            except Exception as exc:
                self.error(exc)

        def generate(self, *_):
            try:
                if self.plan is None:
                    raise MergeError('请先分析合并。')
                self.result_path = self.plan.save(self.output_edit.text().strip())
                self.refresh_log()
                self.open_btn.setEnabled(True)
                self.save_btn.setEnabled(False)
            except Exception as exc:
                self.error(exc)

        def open_output(self, *_):
            try:
                if not self.result_path:
                    return
                app.getPackageMgr().loadUserPackage(self.result_path)
                self.log.appendPlainText(self.t('open_requested'))
            except Exception as exc:
                self.error(MergeError('文件已生成，但自动打开失败。请使用 File > Open 打开：\n' + self.result_path + '\n' + str(exc)))

    _DIALOG = InternalizerDialog()
    _DIALOG.show()


def initializeSDPlugin():
    global _MENU, _UI
    import sd
    from PySide6 import QtGui
    if _MENU is not None:
        return
    _UI = sd.getContext().getSDApplication().getQtForPythonUIMgr()
    _MENU = _UI.newMenu(menuTitle='SBS 依赖工具 / Dependency Tools', objectName='xiaofeng.sbs_dependency_internalizer.menu')
    action = QtGui.QAction('依赖内部化 / Internalize Dependencies…', _MENU)
    action.triggered.connect(_show_dialog)
    _MENU.addAction(action)
    print('[SBS Dependency Internalizer] loaded ' + VERSION)


def uninitializeSDPlugin():
    global _MENU, _DIALOG, _UI
    if _DIALOG is not None:
        _DIALOG.close()
        _DIALOG.deleteLater()
        _DIALOG = None
    if _MENU is not None:
        _MENU.deleteLater()
        _MENU = None
    _UI = None


def main():
    import argparse
    parser = argparse.ArgumentParser(description='自动递归内部化 SBS 依赖中的函数和 Graph，另存结果。')
    parser.add_argument('--host', required=True, help='A.sbs')
    parser.add_argument('--scan', action='store_true', help='只列出 A 的依赖')
    parser.add_argument('--source', help='B.sbs')
    parser.add_argument('--dependency-id', help='扫描结果中的依赖 UID')
    parser.add_argument('--output', help='新的输出 .sbs 路径；不覆盖已有文件')
    parser.add_argument('--collision-policy', choices=('rename', 'replace'), default='rename',
                        help='同名资源处理：rename 保留并更名，replace 覆盖 A 中同类型资源')
    args = parser.parse_args()
    try:
        if args.scan:
            print(json.dumps(scan_dependencies(args.host), ensure_ascii=False, indent=2))
            return
        if not args.output:
            parser.error('合并需要 --output')
        if bool(args.source) != bool(args.dependency_id):
            parser.error('--source 和 --dependency-id 必须同时提供；都不提供时自动分析全部依赖')
        plan = MergePlan(args.host, args.source, args.dependency_id, args.collision_policy)
        print('\n'.join(plan.log))
        result = plan.save(args.output)
        print('\n'.join(plan.generation_log(result)))
        print('已生成：' + result)
    except (MergeError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
