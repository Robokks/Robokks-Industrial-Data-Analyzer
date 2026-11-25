# Account usability correction

Current authentication uses individually created accounts, salted scrypt password hashes and role permissions. Demo mode does not grant Manage users permission. First launch requires a local administrator account; subsequent users are created by an authenticated administrator.

Changes: explicit demo sign-in entry point under account navigation; login password visibility toggle and first-run requirements; responsive scrollable user form; password confirmation, show-password option, inline validation feedback and success message. New interaction test exercises the real Create user button with short, mismatched, valid and duplicate credentials, then authenticates the created engineer against a temporary SQLite database.

The proposed predictable daily master password (brand plus current date/time) is intentionally not added to this corrective revision: a public date is not a secret and such a scheme would weaken every installed administrator account. A separately approved time-based authentication design should use a unique per-installation secret, secure enrollment and recovery, rather than a universal master password. Existing account hashes and permissions are not changed by this UI revision.

Windows validation and new screenshot review are pending.
