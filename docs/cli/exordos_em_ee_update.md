
# exordos_em_ee_update

Update one or more elements

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos em ee update [OPTIONS] [UUID_OR_NAME_OR_PATH]...                                                                                                                                                                                                                                           
                                                                                                                                                                                                                                                                                                           
```

## Options

* `version`:
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-v
--version`

  version of the element

* `y`:
    * Type: boolean
    * Default: `false`
    * Usage: `--yes
-y`

  Automatically answer yes for all questions

* `project_id`:
    * Type: uuid
    * Default: `00000000-0000-0000-0000-000000000000`
    * Usage: `-p
--project-id`

  Project UUID, required only if the upload repository doesn't exist yet

* `timeout`:
    * Type: float
    * Default: `600.0`
    * Usage: `--timeout`

  Seconds to wait for repository upload and element sync to complete

* `uuid_or_name_or_path`:
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `uuid_or_name_or_path`

* `help`:
    * Type: boolean
    * Default: `false`
    * Usage: `--help`

  Show this message and exit.

## CLI Help

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos em ee update [OPTIONS] [UUID_OR_NAME_OR_PATH]...                                                                                                                                                                                                                                           
                                                                                                                                                                                                                                                                                                           
 Update one or more elements                                                                                                                                                                                                                                                                               
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version     -v  TEXT   version of the element                                                                                                                                                                                                                                                         │
│ --yes         -y         Automatically answer yes for all questions                                                                                                                                                                                                                                     │
│ --project-id  -p  UUID   Project UUID, required only if the upload repository doesn't exist yet                                                                                                                                                                                                         │
│ --timeout         FLOAT  Seconds to wait for repository upload and element sync to complete [default: 600.0]                                                                                                                                                                                            │
│ --help                   Show this message and exit.                                                                                                                                                                                                                                                    │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
