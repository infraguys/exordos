
# exordos_metapaas_s3_users_add

Add a new user

## Usage

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 users add [OPTIONS]                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                           
```

## Options

* `uuid`:
    * Type: uuid
    * Default: `none`
    * Usage: `-u
--uuid`

  UUID of the user

* `project_id` (REQUIRED):
    * Type: uuid
    * Default: `sentinel.unset`
    * Usage: `-p
--project-id`

  UUID of the project in which to create the user

* `instance_uuid` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-i
--instance-uuid`

  UUID of the instance to create the user in

* `name` (REQUIRED):
    * Type: text
    * Default: `sentinel.unset`
    * Usage: `-n
--name`

  Name of the user

* `description`:
    * Type: text
    * Default: `none`
    * Usage: `--description`

  Description of the user

* `help`:
    * Type: boolean
    * Default: `false`
    * Usage: `--help`

  Show this message and exit.

## CLI Help

```console
                                                                                                                                                                                                                                                                                                           
 Usage: exordos metapaas s3 users add [OPTIONS]                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                           
 Add a new user                                                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│    --uuid           -u  UUID  UUID of the user                                                                                                                                                                                                                                                          │
│ *  --project-id     -p  UUID  UUID of the project in which to create the user [required]                                                                                                                                                                                                                │
│ *  --instance-uuid  -i  TEXT  UUID of the instance to create the user in [required]                                                                                                                                                                                                                     │
│ *  --name           -n  TEXT  Name of the user [required]                                                                                                                                                                                                                                               │
│    --description        TEXT  Description of the user                                                                                                                                                                                                                                                   │
│    --help                     Show this message and exit.                                                                                                                                                                                                                                               │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
