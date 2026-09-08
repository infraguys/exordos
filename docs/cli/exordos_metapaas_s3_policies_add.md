
# exordos_metapaas_s3_policies_add

Add a new policy

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 policies add [OPTIONS]                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                                                           
```

## Options

* `uuid`:
    * Type: uuid
    * Default: `none`
    * Usage: `-u
--uuid`

  UUID of the policy

* `project_id` (REQUIRED):
    * Type: uuid
    * Default: `sentinel.unset`
    * Usage: `-p
--project-id`

  UUID of the project in which to create the policy

* `instance_uuid` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-i
--instance-uuid`

  UUID of the instance to create the policy in

* `name` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-n
--name`

  Name of the policy

* `description`:
    * Type: text
    * Default: `none`
    * Usage: `--description`

  Description of the policy

* `content` (REQUIRED):
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
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 policies add [OPTIONS]                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                                                           
 Add a new policy                                                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│    --uuid           -u  UUID  UUID of the policy                                                                                                                                                                                                                                                        │
│ *  --project-id     -p  UUID  UUID of the project in which to create the policy [required]                                                                                                                                                                                                              │
│ *  --instance-uuid  -i  TEXT  UUID of the instance to create the policy in [required]                                                                                                                                                                                                                   │
│ *  --name           -n  TEXT  Name of the policy [required]                                                                                                                                                                                                                                             │
│    --description        TEXT  Description of the policy                                                                                                                                                                                                                                                 │
│ *  --content            TEXT  JSON string with the IAM policy document [required]                                                                                                                                                                                                                       │
│    --help                     Show this message and exit.                                                                                                                                                                                                                                               │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
