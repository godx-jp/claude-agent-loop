# agent-loop

Plugin Claude Code để **nhiều session cùng chạy một backlog GitHub issue mà không đạp lên
nhau**. Đơn vị công việc là **một LÔ 10–20 issue**, không phải một issue: mỗi session giành
cả lô bằng khoá nguyên tử, làm trong một worktree duy nhất, mở **một** PR, một session
**khác** review **một lần**, CI chạy **một lần**, rồi merge.

## Vì sao lô, không phải từng issue

Chi phí cố định của một vòng — claim, dựng worktree, review, CI, merge, gc — gần như
**không phụ thuộc số issue trong đó**. Trả chi phí ấy cho từng issue một là nhân nó lên
10–20 lần mà không mua thêm được gì. Đó là lý do một sửa text từng mất cả tiếng mới ship.

| | mỗi issue một vòng | một lô 15 issue |
|---|---|---|
| lần review | 15 | **1** |
| lần CI | 15 | **1** |
| PR phải đọc | 15 | **1** |
| worktree | 15 | **1** |

Đổi lại, một issue hỏng có thể giữ con tin cả lô. Rào cho việc đó là `tal batch drop <N>`:
mỗi commit bắt buộc mang `(#N)`, nên gỡ đúng phần việc của một issue ra là **thao tác cơ
học** — revert commit của nó, trả issue về hàng đợi, 14 issue kia đi tiếp. `tal pr` từ chối
mở PR nếu còn commit không map được về đúng một issue, vì mất khả năng gỡ là mất luôn thứ
khiến gom lô an toàn.

## Full suite không thuộc về vòng lặp

**Cấm, và cấm bằng máy** — `hook-guard` chặn đúng những chuỗi lệnh khai trong `fullSuite`
nếu chúng chạy trong worktree của vòng lặp.

| Chạy gì | Ở đâu | Bao lâu |
|---|---|---|
| **Test liên quan** (`tal tests --run`, theo `affectedTests`) | vai code, vai review, CI của PR lô | giây → phút |
| **Full suite** (`fullSuite`) | CI của PR `dev → main` (`tal release-to-main`), hoặc người gõ `tal fullsuite` | hàng chục phút, **một lần mỗi chu kỳ release** |

Đây là [Test Impact Analysis](https://testing.googleblog.com/) kiểu Google TAP: per-change
chỉ chạy test bị ảnh hưởng, full suite chạy ở cổng gộp và theo chu kỳ. Và nó khớp với
[DORA](https://dora.dev/capabilities/streamlining-change-approval/): duyệt-ngoài hình thức
**âm** với lead time và **không** tương quan với change fail rate — cái giữ được chất lượng
là peer review trong luồng cộng kiểm soát tự động, không phải thêm một cổng nữa.

## Vì sao không dùng label để claim

Label GitHub **không có compare-and-swap**. Hai session đọc "chưa ai nhận" cùng lúc rồi
cùng gắn `status:executing` — cả hai đều thấy mình thắng. Label còn **rò**: session chết là
nhãn ở lại vĩnh viễn.

Primitive nguyên tử duy nhất mà `gh` với tới được là **tạo git ref**:

```sh
gh api repos/O/R/git/refs -f ref=refs/agent-loop/leases/issue-1234 -f sha=<sha>
# lần 2: 422 Reference already exists
```

Bốn tầng độc lập, tầng nào sập tầng khác vẫn chặn:

| Tầng | Chặn được gì | Cơ chế |
|---|---|---|
| 1. Khoá cục bộ | hai session **cùng máy** | `mkdir` nguyên tử trong `~/.tal/` |
| 2. CAS trên ref | hai session **khác máy** | tạo ref → 422 nếu đã có chủ. **Một ref cho MỖI issue**, kể cả khi chúng nằm chung một lô |
| 3. Git | hai worktree cùng branch | `git worktree add` từ chối branch đang checkout |
| 4. Hook | ghi vào worktree không phải của mình; full suite; tên branch lạ | `PreToolUse` |

## Chuẩn tham chiếu

| Vấn đề | Chuẩn áp dụng |
|---|---|
| Loại trừ tương hỗ | **lease** (Gray & Cheriton) trên primitive CAS thật |
| Chủ lease chết | **visibility timeout** kiểu SQS: TTL + heartbeat, hết hạn thì thu hồi |
| Đồng hồ nào là chuẩn | `updated_at` của ledger comment — **đồng hồ server**. Lô dùng sổ của issue **neo**, nên heartbeat chỉ chạm một sổ chứ không chạm 20 |
| Chủ lease treo lâu rồi tỉnh lại | **fencing token** ([Kleppmann](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)): `epoch` đơn điệu tăng, `tal assert` trước mọi lần ghi |
| Kích cỡ lô | **small batch / trunk-based**: lô đủ lớn để nuốt chi phí cố định, đủ nhỏ để còn review nổi trong một lượt |
| Một phần tử hỏng trong lô | **eject**, không huỷ lô (Zuul/Bors, GitHub merge queue): `tal batch drop <N>` |
| Test nào chạy khi nào | **Test Impact Analysis** (Google TAP): per-change chạy test bị ảnh hưởng; full suite ở cổng gộp |
| Bao nhiêu cổng duyệt | **DORA**: peer review trong luồng, KHÔNG thêm cổng duyệt ngoài |
| Issue sửa mãi không xong | **dead-letter** sau `maxAttempts` vòng → chuyển cho người |
| Nội dung review | [Conventional Comments](https://conventionalcomments.org) + mức độ kiểu [Google eng-practices](https://google.github.io/eng-practices/review/reviewer/comments.html): chỉ `(blocking)` mới chặn merge |
| Commit / tiêu đề PR | [Conventional Commits](https://www.conventionalcommits.org) |
| Ai được merge | **tách vai**: session code ≠ session review. Bot ĐƯỢC merge, nhưng chỉ khi review đạt **và** CI của chính PR đó xanh |

## Cài

```
/plugin marketplace add godx-jp/claude-agent-loop
/plugin install agent-loop@godx
/reload-plugins
```

Rồi trong repo của bạn:

```sh
cp <plugin>/examples/agent-loop.json .claude/agent-loop.json   # sửa cho khớp repo
tal doctor --fix        # tạo nhãn agent:*, bật delete_branch_on_merge
tal config              # xem chính sách đã giải
```

Thêm vào `.gitignore`: `.claude/worktrees/` và `.tal-lease.json`.

> **[docs/consumer-guide.md](docs/consumer-guide.md)** — hướng dẫn chi tiết cho repo dùng
> plugin: từng khoá config, cách viết `affectedTests`, hai workflow CI phải có, branch
> protection, đọc exit code, và đường di trú từ mô hình cũ. Đọc nó trước khi chạy thật.

**Bắt buộc khai `affectedTests`** — không có nó thì `tal tests` không suy ra được lệnh nào,
và vai code không còn cách nào chạy test đúng phạm vi.

## Chạy

```
/loop /agent-loop:batch-work       # session code — mỗi lượt một LÔ
/loop /agent-loop:batch-review     # session review — session KHÁC
```

Mở cổng cho bot bằng nhãn `agent:ready`. Không có nhãn đó thì bot bỏ qua.

## Máy trạng thái

```
      người gắn agent:ready
               │
               ▼
         (hàng đợi)  ◄───────────────────────────────┐
               │ tal batch claim  → 10–20 lease      │ lease hết hạn → tal gc thu hồi
               │                    + 1 worktree     │ tal batch drop <N> → trả 1 issue về
               ▼                                     │
       đang thực thi ───────────────────────────-----┘
               │ tal tests --run   (CHỈ test liên quan)
               │ tal pr            → MỘT PR, Closes #… cho cả lô, nhả lease
               ▼
    chờ review (agent:awaiting-review)
               │ tal review-claim (BẮT BUỘC session khác) → MỘT lần cho cả lô
               ▼
       ┌───────┴────────┐
       ▼                ▼
agent:changes-      agent:review-passed
 requested            │ CI của PR (test liên quan) xanh
 (ƯU TIÊN #1)         ▼
       │          tal merge  → base
       └──► claim lại lô     │
        (tối đa maxAttempts) ▼
                       tal gc → xoá branch + worktree, đánh dấu shipped
                              │
                              ▼   khi base đã tích đủ
                       tal release-to-main
                       → PR dev→main → CI chạy FULL SUITE (một lần duy nhất)
```

## Luật tên: đúng hai dạng

| Dạng | Dùng khi |
|---|---|
| `batch-<YYYYMMDD-HHMM>` | đường chính — một lô 10–20 issue |
| `issue-<số>` | issue đứng riêng — **bắt buộc khi chạm submodule** |

Pointer submodule là sha trơ; khi base hỏng ở một pointer, câu hỏi duy nhất là "sha này ra
từ PR nào" — nên nhánh chạm submodule phải mang số issue trong tên, ở repo chính và mọi
repo con, cùng một con số. **Lô bị cấm chạm submodule** (`tal pr` chặn); gặp thì
`tal batch drop <N>` rồi `tal claim <N>` làm riêng.

Truy vết của lô đi đường khác và chặt hơn tên branch: mỗi commit mang `(#N)`, và `tal pr`
từ chối mở PR nếu còn commit không map được về đúng một issue của lô.

Hook chặn mọi tên khác, kể cả qua `git -C <submodule>`.

## Lệnh

| Lệnh | Việc |
|---|---|
| `tal doctor [--fix]` | kiểm điều kiện chạy; `--fix` tạo nhãn + bật `delete_branch_on_merge` |
| `tal config` | in chính sách đã giải (skill đọc lệnh này) |
| `tal queue [-v]` | hàng đợi issue (`-v` kèm lý do bỏ qua) |
| **`tal batch claim [--size N] [--min M] [--issues …]`** | **giành 10–20 issue + dựng MỘT worktree** |
| **`tal batch status`** | issue nào đã có commit, commit nào không map được |
| **`tal batch drop <N> [--reason] [--blocked]`** | **gỡ một issue khỏi lô: revert commit + trả về hàng đợi** |
| **`tal tests [--run] [--pr N]`** | **test LIÊN QUAN theo `affectedTests` — thứ duy nhất vòng lặp được chạy** |
| `tal renew` / `tal assert` | heartbeat / kiểm quyền ghi (fencing) |
| `tal pr` | cổng lô (map commit, không rỗng, không submodule) → push → PR → nhả lease |
| `tal release --state …` | nhả lease: `review` \| `blocked` \| `abandon` \| `no-op` \| `shipped` |
| `tal claim <N> [--split]` | giành MỘT issue — đường của ca chạm submodule |
| `tal submodule <path>` / `submodule-pr` / `submodule-check` | nghi thức repo con |
| `tal review-queue` / `review-claim <PR>` | PR chờ review / giành quyền review |
| `tal review-verdict <PR> pass\|changes` | kết luận review, một lần cho cả lô |
| `tal docs-check <PR>` | PR có cập nhật tài liệu đáng lẽ phải cập nhật chưa |
| `tal merge-queue [-v]` / `tal merge <PR>` | PR đủ điều kiện / merge (review đạt + CI xanh) |
| **`tal release-to-main`** | **mở PR `dev → main` — nơi DUY NHẤT full suite chạy** |
| **`tal fullsuite [--force]`** | full suite do NGƯỜI gõ; từ chối chạy trong worktree vòng lặp |
| `tal gc [--dry-run]` | thu hồi lease chết + xoá branch/worktree sau merge |
| `tal status` | bảng điều phối: ai giữ lô nào, còn bao lâu |
| `tal unlock <key> --force` | can thiệp tay khi chắc session giữ lease đã chết |

Biến môi trường ghi đè config: `TAL_TTL`, `TAL_MAX_ATTEMPTS`, `TAL_BASE`, `TAL_MAIN`,
`TAL_BATCH_MIN`, `TAL_BATCH_MAX`, `TAL_REF_NS`, `TAL_GRACE`, `TAL_SESSION`.

## Dọn rác

`tal gc` chạy đầu mỗi lượt của cả hai vai:

- thu hồi lease im lặng quá TTL (dead-letter nếu tái diễn `maxAttempts` lần);
- xoá **branch remote của mọi PR đã merge** — repo chính và cả submodule;
- xoá worktree + branch cục bộ khi PR đã merge (`--close` đóng luôn issue);
- **không** xoá worktree còn thay đổi chưa commit — nó báo và bỏ qua;
- worktree của lô mà lease đã bị thu hồi thì chỉ **báo**, không xoá;
- PR đóng mà không merge thì chỉ **báo** — cần `--include-abandoned`.

## Yêu cầu

`git`, `gh` (đã `gh auth login`), `python3` (chỉ stdlib). Không cần `jq`, không cần `flock`.

`tal` đọc `CLAUDE_CODE_SESSION_ID` để biết session nào là session nào. Thiếu biến đó thì
rào "review phải khác session code" yếu đi, `tal doctor` sẽ cảnh báo.

## Phiên bản

`plugin.json` **cố ý không có** `version`: plugin dùng commit SHA làm phiên bản, nên mỗi
commit là một bản mới và `/plugin update` luôn lấy được bản mới nhất.
