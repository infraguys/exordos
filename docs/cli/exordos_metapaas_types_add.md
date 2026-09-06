
# exordos_metapaas_types_add

Add a new type

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas types add [OPTIONS]                                                                                                                                                                                                                                                               
                                                                                                                                                                                                                                                                                                           
```

## Options

* `uuid`:
    * Type: uuid
    * Default: `none`
    * Usage: `-u
--uuid`

  UUID of the type

* `project_id` (REQUIRED):
    * Type: uuid
    * Default: `sentinel.unset`
    * Usage: `-p
--project-id`

  UUID of the project in which to register the type

* `name` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-n
--name`

  Name of the type, the PaaS slug, for example: s3

* `description`:
    * Type: text
    * Default: `none`
    * Usage: `--description`

  Description of the type

* `element_name` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-e
--element-name`

  Name of the element the PaaS is exposed under, for example: s3aas

* `package` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `--package`

  Pip distribution name, a wheel/sdist URL or an urn:artifacts:<uuid>

* `version`:
    * Type: text
    * Default: `none`
    * Usage: `-v
--version`

  Version pin of the package

* `index_url`:
    * Type: text
    * Default: `none`
    * Usage: `--index-url`

  Pip index URL to install the package from

* `help`:
    * Type: boolean
    * Default: `false`
    * Usage: `--help`

  Show this message and exit.

## CLI Help

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas types add [OPTIONS]                                                                                                                                                                                                                                                               
                                                                                                                                                                                                                                                                                                           
 Add a new type                                                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│    --uuid          -u  UUID  UUID of the type                                                                                                                                                                                                                                                           │
│ *  --project-id    -p  UUID  UUID of the project in which to register the type [required]                                                                                                                                                                                                               │
│ *  --name          -n  TEXT  Name of the type, the PaaS slug, for example: s3 [required]                                                                                                                                                                                                                │
│    --description       TEXT  Description of the type                                                                                                                                                                                                                                                    │
│ *  --element-name  -e  TEXT  Name of the element the PaaS is exposed under, for example: s3aas [required]                                                                                                                                                                                               │
│ *  --package           TEXT  Pip distribution name, a wheel/sdist URL or an urn:artifacts:<uuid> [required]                                                                                                                                                                                             │
│    --version       -v  TEXT  Version pin of the package                                                                                                                                                                                                                                                 │
│    --index-url         TEXT  Pip index URL to install the package from                                                                                                                                                                                                                                  │
│    --help                    Show this message and exit.                                                                                                                                                                                                                                                │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
