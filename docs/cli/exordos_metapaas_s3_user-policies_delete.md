
# exordos_metapaas_s3_user-policies_delete

Delete policy attachment

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 user-policies delete [OPTIONS] UUID...                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                                                           
```

## Options

* `uuid` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `uuid`

* `y`:
    * Type: boolean
    * Default: `false`
    * Usage: `--yes
-y`

  Automatically answer yes for all questions

* `user_uuid` (REQUIRED):
    * Type: uuid
    * Default: `sentinel.unset`
    * Usage: `--user-uuid`

* `instance_uuid` (REQUIRED):
    * Type: uuid
    * Default: `sentinel.unset`
    * Usage: `--instance-uuid`

* `help`:
    * Type: boolean
    * Default: `false`
    * Usage: `--help`

  Show this message and exit.

## CLI Help

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 user-policies delete [OPTIONS] UUID...                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                                                           
 Delete policy attachment                                                                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│    --yes            -y        Automatically answer yes for all questions                                                                                                                                                                                                                                │
│ *  --user-uuid          UUID  [required]                                                                                                                                                                                                                                                                │
│ *  --instance-uuid      UUID  [required]                                                                                                                                                                                                                                                                │
│    --help                     Show this message and exit.                                                                                                                                                                                                                                               │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
