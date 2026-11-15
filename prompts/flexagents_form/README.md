# Paste into FlexAgents sub-agent form

For each sub-agent, fill the UI fields from the matching file.

**First:** Tools tab → create an HTTP connection to  
`https://access-la-flexagents-api.vercel.app`  
(and a Knowledge base connection for `answer_policy`).  
Until a connection exists, “What it can look up” stays empty.

| Sub-agent | Form file |
|-----------|-----------|
| answer_policy | `answer_policy.md` |
| find_department | `find_department.md` |
| log_case | `log_case.md` |
| book_callback | `book_callback.md` |

Copy **only the text under each numbered section** into the matching UI box.  
Model: **low** for all four.
