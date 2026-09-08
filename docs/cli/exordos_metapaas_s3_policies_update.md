
# exordos_metapaas_s3_policies_update

Update policy

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 policies update [OPTIONS] UUID                                                                                                                                                                                                                                                 
                                                                                                                                                                                                                                                                                                           
```

## Options

* `uuid` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `uuid`

* `instance_uuid` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-i
--instance-uuid`

  UUID of the instance the policy belongs to

* `name`:
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-n
--name`

  Name of the policy

* `description`:
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `--description`

  Description of the policy

* `content`:
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `--content`

  JSON string with the IAM policy document

* `help`:
    * Type: boolean
    * Default: `false`
    * Usage: `--help`

  Show this message and exit.

## CLI Help

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 policies update [OPTIONS] UUID                                                                                                                                                                                                                                                 
                                                                                                                                                                                                                                                                                                           
 Update policy                                                                                                                                                                                                                                                                                             
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --instance-uuid  -i  TEXT  UUID of the instance the policy belongs to [required]                                                                                                                                                                                                                     │
│    --name           -n  TEXT  Name of the policy                                                                                                                                                                                                                                                        │
│    --description        TEXT  Description of the policy                                                                                                                                                                                                                                                 │
│    --content            TEXT  JSON string with the IAM policy document                                                                                                                                                                                                                                  │
│    --help                     Show this message and exit.                                                                                                                                                                                                                                               │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
