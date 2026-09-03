# SBS Dependency Internalizer

[English](README.md) | [中文](README_zh.md)

SBS Dependency Internalizer is a Substance 3D Designer 16 / PySide6 plugin that makes editable `.sbs` dependency chains portable. It discovers the functions and material graphs actually used by package A, resolves nested packages recursively, and merges them from the deepest dependency back toward A: `D → C`, `C → B`, then `B → A`.

Compiled `.sbsar` packages cannot be decompiled, so the plugin handles them like Designer's **Export with dependencies** command: it copies them beside the generated SBS and rewrites package references to relative paths. The compatibility extension `.sbser` is accepted as well.

The plugin uses Designer's bundled Python and PySide6 plus the Python standard library. It does not require the Substance Automation Toolkit, PySBS, or a network connection.

## Highlights

- Automatically discovers all reachable editable SBS dependencies.
- Supports nested chains, branches, duplicate paths, and cyclic package references.
- Copies only reachable functions and ordinary material graphs; unrelated resources are not imported.
- Processes packages bottom-up so each intermediate result participates in the next merge stage.
- Shows the dependency hierarchy and every merge stage in an expandable tree.
- Provides a per-resource collision selector:
  - **Add `_from_*`** keeps both resources and gives the imported resource a deterministic suffix.
  - **Replace same-name resource** redirects references to the incoming resource.
- Preserves A's existing instance nodes, parameters, dynamic values, inheritance settings, layout, and connections.
- Remaps conflicting structural UIDs without rewriting unrelated numeric or string constants.
- Preserves multi-output graph bridges and existing output connections.
- Migrates resolvable `.sbsar` / `.sbser` dependencies into `<output-name>_dependencies` and writes relative references.
- Keeps Designer built-in dependencies such as `sbs://functions.sbs` external and hides them from the analysis tree.
- Produces a detailed generation log for each merge, rename, replacement, migration, and final write.
- Offers live Chinese / English UI switching and remembers the selected language.
- Never overwrites source packages or an existing output file.

## Requirements

- Adobe Substance 3D Designer 16 or a compatible release using PySide6.
- A saved `.sbs` target package.
- Editable dependency packages must be available as saved `.sbs` files if their contents are to be internalized.
- All editable SBS files in one merge must use the same `formatVersion`. Open and save them with the same Designer version if necessary.

## Repository contents

| Path | Purpose |
| --- | --- |
| `SBSDependencyInternalizer.py` | Designer plugin entry point. |
| `DependencyInternalizer.py` | XML analysis, merge engine, migration logic, CLI, and PySide6 UI. |
| `pluginInfo.json` | Plugin metadata and minimum Designer version. |
| `README.md` | English documentation. |
| `README_zh.md` | Chinese documentation. |
| `tests/` | Standard-library regression tests and small test fixtures. |

The local `dependency_text/` directory is intentionally excluded from the repository because it contains user-provided packages, generated results, autosaves, and compiled assets.

## Installation

### Plugin Manager

1. Download or clone this repository to a permanent folder.
2. In Designer, open **Tools → Plugin Manager**.
3. Choose **Browse**, select `SBSDependencyInternalizer.py`, and load it.
4. Open **SBS Dependency Tools / SBS 依赖工具 → Internalize Dependencies / 依赖内部化…**.

### Python plugin search path

If your Designer build does not provide a `.py` Browse action:

1. Open **Edit → Preferences → Projects**.
2. Select the active Project File and open its **Python** settings.
3. Add the folder containing `SBSDependencyInternalizer.py` to the plugin search path.
4. Restart Designer and load the plugin from Plugin Manager.

This is a Python source plugin. Do not install an ordinary ZIP archive as an `.sdplugin` package.

## Usage

1. Save A and every editable dependency package in Designer. The plugin reads files from disk and cannot see unsaved edits.
2. Open the plugin and choose A, or use **Current graph package**.
3. Optionally switch between **中文** and **English** at the top of the window.
4. Select **1. Analyze**.
5. Review the dependency tree. For every name collision, select either **Add `_from_*`** or **Replace same-name resource**. Changing a choice recalculates downstream stages.
6. Choose a new output `.sbs` path.
7. Select **2. Generate SBS**.
8. Review the step-by-step log, then use **Open generated file** and verify the corresponding graph in Designer's Explorer.

The generated package receives a new `fileUID`, so it can remain open alongside A.

## Merge model

For a chain where A uses B, B uses C, and C uses D, generation is modeled as:

```text
D → C
C (including D's result) → B
B (including C and D's result) → A
```

Only function and graph resources reachable from actual instance references are included. If A also directly references C or D, those references are redirected into the same internalized result and redundant editable package dependencies are removed.

Cycles are deduplicated. A resource already visited through another branch is not copied repeatedly.

## Name collision handling

Collision choices are evaluated at each merge stage rather than only at the final A package:

- **Add `_from_*`** is the default. A resource such as `Functions/noise` may become `Functions/noise_from_C`. Numeric suffixes are added if that name also exists.
- **Replace same-name resource** makes the incoming resource the survivor for that stage and updates dependent references accordingly.

The tree shows the planned result before any file is written. Source packages are never modified.

## SBSAR / SBSER dependency migration

Resolvable compiled dependencies are retained as packages rather than internalized. When generating `Material_internalized.sbs`, the plugin creates:

```text
Material_internalized.sbs
Material_internalized_dependencies/
  dependency.sbsar
```

The generated SBS references `Material_internalized_dependencies/dependency.sbsar` with forward-slash relative paths. When different source files share the same filename, later files receive `_2`, `_3`, and similar suffixes.

For safety, generation stops if the destination dependency directory already exists. Choose another output filename instead of overwriting that directory. Missing compiled packages and Designer path aliases remain external because there is no local file to copy.

SBSAR is a compiled, one-way format. The plugin does not and cannot reconstruct its editable graphs; obtain the original SBS if those resources need to be merged.

## Safety and validation

- The output must be a new `.sbs` file.
- Existing outputs and existing migration directories are not overwritten.
- Input SBS files are hashed during analysis. Generation stops if one changes before writing.
- DTD and ENTITY declarations are rejected before XML parsing.
- Package dependency IDs, internal resource references, function inputs, graph outputs, local node links, and dynamic-function roots are validated.
- On a migration or write failure, newly created dependency copies are removed when possible so a partial export is not presented as a valid result.
- If A contains directly embedded media resources, the output must remain in A's folder so existing relative media paths do not silently change.

Always open the generated package in Designer and verify the graph output before replacing a production asset.

## Supported scope and limitations

Supported:

- Editable SBS function instances.
- Ordinary material graph instances.
- Recursive editable SBS package dependencies.
- Multi-output graph bridging.
- External compiled package migration for `.sbsar` and `.sbser`.

Not currently internalized:

- Bitmap, SVG, mesh, font, or other external media resources inside an imported function or graph.
- Unknown serialized package-reference fields.
- Designer aliases that cannot be resolved to a local file.
- Missing files.
- SBSAR graph contents.

For unsupported content in a package selected for internalization, the operation stops with an error instead of silently producing an incomplete merge.

## Command line

The XML merge core can run with standard Python without importing PySide6 or Designer.

Analyze and merge every editable dependency:

```powershell
python DependencyInternalizer.py `
  --host "D:/Materials/A.sbs" `
  --output "D:/Materials/A_internalized.sbs"
```

Use replacement as the default collision policy:

```powershell
python DependencyInternalizer.py `
  --host "D:/Materials/A.sbs" `
  --output "D:/Materials/A_internalized.sbs" `
  --collision-policy replace
```

List A's external dependencies:

```powershell
python DependencyInternalizer.py --host "D:/Materials/A.sbs" --scan
```

To process only one direct source, provide both `--source` and `--dependency-id`.

## Tests

Run the standard-library test suite from the repository root:

```powershell
python -m unittest discover -s tests -v
python -m py_compile DependencyInternalizer.py SBSDependencyInternalizer.py
```

The current suite contains 24 regression tests covering recursive discovery, bottom-up merge ordering, branches and cycles, UID remapping, per-stage collision choices, output bridging, file-change detection, compiled-package migration, relative-path rewriting, bilingual log output, and overwrite protection.

## Troubleshooting

### `ModuleNotFoundError: No module named 'SBSDependencyInternalizer'`

Keep `SBSDependencyInternalizer.py` and `DependencyInternalizer.py` in the same directory, then add that directory—not an individual file or a ZIP—to Designer's Python plugin search path. Restart Designer after changing the path.

### Analyze reports no editable dependencies

Confirm the dependencies are saved `.sbs` files, their paths resolve from A, and A actually contains function or graph instances referencing them. A project with only a resolvable `.sbsar/.sbser` dependency can still use migration-only mode.

### The generated package cannot find a compiled dependency

Move the generated `.sbs` together with its matching `<output-name>_dependencies` directory. Do not separate or rename one without updating the relative references.

### Generation says an input changed

Save all packages, run **Analyze** again, recheck collision choices, and generate a new output filename.

### English mode still shows Chinese text

Plugin UI text and log messages are translated. User filenames and filesystem paths are intentionally preserved exactly, so Chinese characters inside an asset name or directory remain visible.

## Technical notes

The plugin edits saved SBS XML rather than rebuilding Designer nodes through the runtime API. Only known function-instance and graph-instance reference fields are rewritten. Structural UIDs are remapped within imported resources when they collide, while unrelated constants remain untouched.

## Adobe references

- [Plugin basics](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/scripting/plugin-basics)
- [Creating user interface elements](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/scripting/creating-user-interface-elements)
- [Project settings and plugin search paths](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/workspace/preferences/project-settings)
- [Publishing SBSAR files](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/substance-graphs/publishing-substance-3d-asset-files-sbsar)

## Status

Version: **1.7.0**

The XML core is covered by automated tests. The plugin should still be validated in the exact Designer build and project configuration used for production.
