# Campus data templates

Fill these in at your own pace and send them over. Open them in Excel or Google Sheets and save as CSV.

- **`rooms.csv`**: classrooms, labs, washrooms and offices in each block, so students can pick the exact spot.
- **`people.csv`**: who handles which kind of problem, and where, so each report reaches the right person.

The `*_example.csv` files show filled-in rows. Their names and numbers are made up, so don't copy them into the real files.

## Routing rule (agreed)
When a report's **place** and **category** match **exactly one main person** (`backup` = no), the ticket is assigned to that person automatically and they're notified. If nobody matches, or more than one main person does, a coordinator decides. Backup people are used when the main person is away.

## `rooms.csv`

| Column | What to write | Example |
| --- | --- | --- |
| `place_key` | Which block or facility (codes listed below) | `cse-block` |
| `floor` | Floor number, with 0 for the ground floor | `2` |
| `room_name` | The name people use for it | `Room 204`, `Lab 3 (Computer Lab)` |
| `room_type` | One of: classroom, lab, washroom, office, staff room, seminar hall, exam hall, corridor, store room, other | `lab` |
| `department` | The department that uses it (optional) | `CSE` |
| `notes` | Anything useful (optional) | `60 systems` |

## `people.csv`

| Column | What to write | Example |
| --- | --- | --- |
| `full_name` | Full name | `Ravi Kumar` |
| `job_title` | Their actual job | `Electrician`, `Plumbing supervisor` |
| `app_role` | `STAFF` for people who fix things, `COORDINATOR` for people who check and assign reports | `STAFF` |
| `department` | Their maintenance department | `Electrical Maintenance` |
| `email` | Email for their account and notifications | `ravi@mvsrec.edu.in` |
| `phone` | Mobile number (shown only to coordinators and admins) | `9000000001` |
| `places` | Place codes they cover, separated by `;`, or `all` | `cse-block;civil-block` |
| `categories` | Kinds of problem they handle, separated by `;`, or `all` (list below) | `Electrical` |
| `backup` | `no` for the main person, `yes` for someone who covers when they're away | `no` |
| `working_hours` | When they're available (optional) | `Mon-Sat 9:00-17:00` |
| `notes` | Anything useful (optional) | `covers when Ravi is away` |

## Place codes

| Code | Place |
| --- | --- |
| `as-block` | AS&H Block (First-year block), when it isn't clear whether it's AS1 or AS2 |
| `as1` | AS1 |
| `as2` | AS2 (Exam Branch) |
| `cse-block` | CSE Block |
| `mechanical-block` | Mechanical Block |
| `civil-block` | Civil Block (administrative block, Principal's office) |
| `ece-block` | ECE Block |
| `canteen` | Canteen |
| `library` | Library |
| `placement-cell` | Placement Cell |
| `ground` | Ground (Playground) |
| `basketball-ground` | Basketball Ground |
| `parking-area` | Parking Area |
| `indoor-sports-room` | Indoor Sports Room (on top of the canteen building) |
| `boys-hostel` | Boys' Hostel |
| `girls-hostel` | Girls' Hostel |

If a place is missing, write its name in `notes` and we'll add a code.

## Problem categories
`IT / Network`, `Electrical`, `Sanitation`, `Water / Plumbing`, `Classroom Equipment`, `Civil Maintenance`, `Academic Facilities`, `Other`

Use these exact spellings. If a category doesn't fit how the college splits the work, tell us and we'll change the list.
