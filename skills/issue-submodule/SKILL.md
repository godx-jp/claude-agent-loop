---
name: issue-submodule
description: "Nghi thức sửa git submodule trong vòng lặp issue. Issue chạm submodule KHÔNG đi đường lô — nó đi một mình qua `tal claim <N>`: branch issue-<số> y hệt ở repo chính và repo con, PR riêng nhắm đúng nhánh mà repo chính theo dõi, pointer chỉ bump sau khi đã push. Dùng khi issue phải sửa code trong submodule, khi `tal pr` chặn vì lô chạm submodule, hoặc khi tal báo lỗi pointer / quên bump / chưa push."
---

# issue-submodule — chạm repo con thì làm đúng nghi thức

**Đây là đường ĐƠN, không phải đường lô.** Lô (`batch-<…>`) bị `tal pr` **chặn** nếu chạm
submodule: pointer submodule là sha trơ nên nhánh chạm nó phải mang số issue trong tên, mà
tên lô thì không mang được. Gặp trong lô thì gỡ ra rồi làm riêng:

```sh
tal batch drop <N> --reason "chạm submodule"
tal claim <N>
```

Kích hoạt khi issue bạn đang giữ lease phải sửa code nằm trong submodule. Yêu cầu trước:
đã `tal claim` và đang ở trong worktree `issue-<N>`.

## Luật tên — tuyệt đối

**Branch trong submodule PHẢI trùng tên với branch repo chính: `issue-<số>`.** Cùng một
con số, ở mọi repo. Không slug, không `feat/`, không `fix/`, không hậu tố.

Vì sao không phải thẩm mỹ: pointer submodule là một **sha trơ**, không mang thông tin.
Khi base branch hỏng ở một pointer, câu hỏi duy nhất cần trả lời là "sha này ra từ PR
nào" — nếu mọi nhánh đều tên `issue-<số>` thì tra một bước ở mọi repo. Đặt tên tự do là
mất hẳn khả năng đó.

**Cần một nhánh nữa thì mở sub-issue** và dùng số của sub-issue đó
(`tal claim <sub> --split`). Không có đường nào khác.

Luật này cưỡng chế bằng máy: hook `PreToolUse` chặn `git checkout -b`, `git switch -c`,
`git branch`, `git worktree add -b` và `git push src:refs/heads/…` với mọi tên không khớp
`^issue-\d+$`, **kể cả `git -C <submodule>`**. Đừng tìm cách lách; `tal submodule` tạo
đúng tên sẵn.

## Thứ tự bắt buộc: push repo con TRƯỚC, bump pointer SAU

Đảo thứ tự là commit một pointer chưa tồn tại trên remote → **mọi lần clone mới đều chết**
ở `git submodule update`, và người phát hiện thường không phải người gây ra.

```sh
tal submodule <path>        # 1. init + tạo branch issue-N trong repo con
cd <path> && git add … && git commit -m "fix(scope): …" && cd -
tal submodule-pr <path>     # 2. push repo con + mở PR ở repo con  ← TRƯỚC bump
git add <path> && git commit -m "chore(<path>): bump to <sha>"   # 3. bump pointer ← SAU
tal submodule-check         # 4. tự soi; `tal pr` cũng gọi cổng này
```

Chạm nhiều submodule thì lặp 1→3 cho từng cái, rồi `submodule-check` một lần.

## PR của repo con nhắm nhánh mà repo chính theo dõi

`tal submodule-pr` lấy base từ trường `branch` trong `.gitmodules` — **không** lấy
`default_branch` của GitHub. Cố ý: nhiều repo để default là `main` và gắn CI/CD
auto-deploy vào đó, nên merge một PR review vào `main` là **đẩy thẳng production**. Đừng
tự `gh pr create -R <repo con>` bằng tay; dùng `tal submodule-pr`.

Repo nào thật sự muốn default branch thì khai `"submodulePrBase": "default"` trong
`.claude/agent-loop.json` — đó là quyết định của người, không phải của bạn.

## Đọc lỗi từ `tal submodule-check`

`tal pr` gọi cổng này và **từ chối mở PR** nếu còn lỗi. Năm loại, đều là hỏng thật:

| kind | nghĩa | cách sửa |
|---|---|---|
| `dirty` | repo con còn file chưa commit → pointer chắc chắn sẽ lệch | commit trong repo con |
| `branch` | repo con không ở `issue-<N>` | `tal submodule <path>` |
| `pointer` | pointer repo chính ≠ HEAD repo con → **quên bump**, hoặc bump nhầm commit | `git add <path> && git commit` |
| `unpushed` | pointer trỏ sha chưa có trên `origin/issue-<N>` → ai clone cũng chết | `tal submodule-pr <path>` |
| `no-pr` | chưa có PR nào cho `issue-<N>` ở repo con → thay đổi sẽ không ai review | `tal submodule-pr <path>` |

Không tự ý `--skip-submodule-check`, và không `git commit --no-verify` để vượt git hook
của repo. Cả hai đều là tắt đúng cái lưới đang bảo vệ base branch.

## Ghi vào thân PR của repo chính

Liệt kê rõ từng PR con, để người merge biết thứ tự:

```md
## Submodule
- <owner>/<repo-con>#42 (`<path>`) → pointer `a1b2c3d`
```

**Thứ tự merge: PR con trước, PR chính sau.** Pointer đang trỏ một commit trên
`issue-<N>` của repo con; nếu repo chính merge trước thì base branch mang pointer nằm
ngoài base branch của repo con — vẫn clone được khi branch còn sống, nhưng thành dangling
ngay khi branch đó bị xoá sau merge. Nói rõ thứ tự này trong thân PR.

## Nếu git hook của repo báo pointer đã push là "dangling"

Cạm bẫy đã gặp thật, đáng biết trước: git **xuất `GIT_DIR` cho hook**, và `GIT_DIR`
**thắng cả `-C`**. Nên `git -C <submodule> …` viết trong một git hook KHÔNG chạy trong
submodule. Ở worktree gốc `GIT_DIR` là `".git"` tương đối nên tình cờ giải đúng; trong
**worktree phụ** (vòng lặp này luôn sống ở đó) `GIT_DIR` là đường dẫn tuyệt đối nên mọi
lookup rơi vào repo chính, và một pointer đã push đàng hoàng vẫn bị báo dangling.

Cách sửa cho hook của repo:
`env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C "$path" …`.
Đừng "sửa" bằng `--no-verify` — cái hook đang kiểm là thứ có thật.

## Chỉ submodule THẬT SỰ đổi mới cần branch

Không phải "chạm issue là tạo branch ở cả 7 repo con". Chỉ repo con nào có file thay đổi
mới cần `tal submodule <path>` + PR riêng. Sau một lệnh codegen chạm nhiều repo con (ví dụ
`omnify:gen` ở kho đo được), kiểm bằng `git status --short` xem đúng những submodule nào
hiện lên — chỉ tạo branch cho chúng.
`tal submodule-check` cũng chỉ xét submodule đã bị chạm: submodule chưa init, hoặc pointer
và HEAD còn bằng base, đều được bỏ qua chứ không bị đòi branch.

## Conflict gitlink — giải theo BẢNG, không giải theo cảm tính

Conflict pointer submodule là loại conflict thường gặp nhất của repo đa module, và nó có
**đáp án xác định** trong hầu hết trường hợp. Đừng đoán, đừng "lấy bên mình".

```sh
DEVP=$(git ls-tree origin/<base> <path> | awk '{print $3}')      # pointer phía base
PRP=$(git ls-tree HEAD <path>            | awk '{print $3}')      # pointer phía nhánh mình
TIP=$(git -C <path> rev-parse origin/<base-repo-con>)             # tip dev của repo con
git -C <path> merge-base --is-ancestor $DEVP $TIP && echo "dev ⊂ tip"
git -C <path> merge-base --is-ancestor $PRP  $TIP && echo "PR  ⊂ tip"
```

| Tình huống | Giải thế nào |
|---|---|
| tip `dev` repo con chứa **cả hai** phía | **lấy tip** — đáp án duy nhất không mất việc bên nào |
| một bên là **tổ tiên** của bên kia | lấy **hậu duệ** |
| còn lại (phân kỳ thật, chưa merge) | **người quyết** — merge PR con trước rồi giải lại |

Ca 1 là ca thường: PR con đã merge vào `dev` repo con, còn pointer umbrella vẫn trỏ commit
**trước merge**. Không phải ngoại lệ — đó là hình dạng bình thường của mọi thay đổi đa repo.

Đặt gitlink **không cần checkout submodule**:

```sh
git update-index --cacheinfo 160000,<sha>,<path>
git diff --name-only --diff-filter=U      # phải rỗng
```

**`Failed to merge submodule <path> (not checked out)` KHÔNG phải conflict thật.** Git chỉ
đang nói nó không mở được repo con để trộn. Init submodule, hoặc giải thẳng bằng
`update-index` như trên.

Kiểm sống trên #1318: `dev` trỏ `e3ddc4936`, nhánh trỏ `56ecbe27b`, **phân kỳ** — nhưng
`admin-web/dev` (tip `5bf8b23c1`) chứa cả hai ⇒ lấy tip ⇒ PR chuyển từ `CONFLICTING` sang
`MERGEABLE`, không đổi một dòng code nào.

## Dọn

Sau khi PR con merge, `tal gc` xoá branch `issue-<N>` ở **cả** repo con và repo chính.
Bật `delete_branch_on_merge` cho mọi repo (`tal doctor --fix` làm việc này) thì GitHub tự
xoá, `tal gc` hứng phần sót. Không tự xoá branch repo con khi PR chính chưa merge —
pointer sẽ thành dangling.
