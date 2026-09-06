---
name: batch-work
description: "Vai CODE của vòng lặp issue tự động (tal). Nhặt MỘT LÔ 10–20 issue từ hàng đợi GitHub, giành lease nguyên tử cho cả lô, dựng một worktree duy nhất, sửa hết, chạy TEST LIÊN QUAN (không bao giờ full suite), mở MỘT PR rồi bàn giao cho session review. Dùng khi người nói chạy vòng lặp issue, xử lý backlog tự động, /loop /batch-work, hoặc khi cần sửa tiếp một lô bị review yêu cầu sửa."
---

# batch-work — vai CODE

**Một lần gọi = một LÔ, không phải một issue.** `/loop` điều phối nhịp, không phải bạn.

Vì sao gom lô: chi phí cố định của một vòng (claim, review, CI, merge, gc) gần như không
phụ thuộc số issue trong đó. Trả chi phí ấy cho từng issue một là nhân nó lên 10–20 lần —
đó là lý do một sửa text từng mất cả tiếng mới ship được.

CLI là `tal`. Mọi lệnh chạy từ gốc repo, trừ khi đang ở trong worktree của lô.

---

## Bước 0 — chính sách

```sh
tal config
```

Đọc `policyDocs` (`work`, `test`). Thiếu file → nói ra, làm theo luật chung, đề nghị người
viết. Tool mang cơ chế; chính sách nằm ở đó.

## Bước 1 — lập lô

```sh
tal gc
tal batch claim --json      # mặc định 10–20 issue, đã xếp sẵn thứ tự đúng
```

- Hàng đợi **đã xếp hạng**: changes-requested trước → severity → số nhỏ trước. Đừng chọn
  lại theo cảm tính.
- exit **75** = chưa đủ `min` issue đủ điều kiện, hoặc bị session khác giành mất. **Không
  phải lỗi.** Nói rõ còn bao nhiêu, kết thúc lượt.
- Issue chỉ vào hàng đợi khi người đã gắn nhãn `ready`. Thiếu nhãn đó là **cố ý** — đừng
  `--force` để lách.
- **Issue chạm submodule KHÔNG đi đường lô** (tal chặn ở `tal pr`). Gặp thì
  `tal batch drop <N> --reason "chạm submodule"` rồi làm riêng bằng `tal claim <N>` +
  skill `issue-submodule`.

```sh
cd <worktree>
tal assert          # đọc lại: mình có thật đang giữ lô này không
```

`tal assert` báo mất thẻ `.tal-lease.json` trong khi lease vẫn sống → `tal adopt` dựng lại
thẻ từ sổ. Nó **không** bump epoch và **không** giành thêm gì; đó là lý do nó an toàn còn
`tal claim` lại thì không.

Issue đứng riêng (`tal claim <N>`) mà bạn biết trước nó sẽ ngồi lên một vùng file đang có
người làm: khai vùng ra — `tal claim <N> --region backend/app/Services`. Chồng lấn với một
lease đang sống thì tal **từ chối**, thay vì để hai session phát hiện nhau lúc merge.

## Bước 2 — với TỪNG issue trong lô

Thứ tự trong một issue, không đảo:

```sh
gh issue view <N> --comments                   # đã ai làm/kết luận gì chưa
git log --oneline --all --grep="#<N>"          # đã có commit nào nhắc issue này chưa
git merge-base --is-ancestor <sha> origin/<base> && echo "CÓ trên base"
```

Bốn kết cục, chọn đúng một:

| Tình huống | Làm gì |
|---|---|
| Code đã có trên base | `tal batch drop <N> --reason "đã ship ở <sha>, kiểm bằng merge-base"` |
| Chờ người quyết / chờ ops | `tal batch drop <N> --blocked --reason "chờ ai / chặn bởi gì"` |
| Phạm vi quá lớn cho một commit | `tal batch drop <N>` + tách sub-issue theo tầng |
| Có việc thật | sửa, rồi commit |

**Mỗi commit BẮT BUỘC mang `(#N)` trong tiêu đề, và chỉ MỘT số issue.**

```sh
git commit -m "fix(i18n): sửa nhãn nút Lưu (#1234)"
```

Đây không phải thẩm mỹ: `tal batch drop` gỡ đúng phần việc của một issue ra khỏi lô dựa
trên số đó. Commit không map được về đúng một issue → `tal pr` **chặn**, vì mất khả năng
gỡ là mất luôn thứ khiến gom lô an toàn.

Gọi `tal renew` sau mỗi bước dài (mỗi lần chạy test, mỗi ~10 phút).

**Chỉ sửa trong worktree mà `tal batch claim` in ra.** Không `cd` về repo gốc.

## Bước 3 — test LIÊN QUAN

```sh
tal batch status        # issue nào đã có commit, commit nào lạc
tal tests               # xem lệnh test liên quan suy ra từ affectedTests
tal tests --run         # chạy chúng
```

**Full suite BỊ CẤM.** Không phải lời khuyên — `hook-guard` chặn thật. Nó chạy ở CI của PR
vào `promotionBranch` (`tal release-to-main`), hoặc do người gõ `tal fullsuite` từ gốc repo.

Test đỏ mà không sửa được → gỡ issue gây đỏ ra khỏi lô (`tal batch drop`) hoặc nói thẳng
trong thân PR. **Đừng mở PR khoe xanh.**

Cạm bẫy đáng biết: test có thể chạy trên engine khác production (SQLite vs MySQL). Thay
đổi **DDL** thì kiểm thêm trên engine thật, và nói rõ đã kiểm ở đâu.

## Bước 4 — MỘT PR cho cả lô

```sh
tal assert
tal pr --title "chore: lô <id> — N issue" --body-file <file>
```

`tal pr` tự: kiểm mọi commit map được về một issue → kiểm không issue nào rỗng → kiểm
không chạm submodule → push `--force-with-lease` → mở/**cập nhật** PR → chèn `Closes #N`
cho cả lô → nhả lease → chuyển sang chờ review.

Thân PR phải có, **theo từng issue**:

```md
## #1234 — sửa nhãn nút Lưu
sửa gì / vì sao / lệnh test đã chạy + kết quả thật

## #1235 — …
```

cộng một mục chung: **phần cố ý không làm**, và **issue đã bị drop kèm lý do**.

```sh
tal docs-check <PR>
```

Đổi quy ước / đổi hành vi người dùng thấy được / thêm cạm bẫy mới / đổi API mà không regen
tài liệu — đều là điểm chặn ở review. Cố ý không cập nhật doc thì **viết ra trong thân PR**.

## Vòng sửa theo review

Lô bị `changes` thì worktree vẫn còn. Nhận lại bằng `tal batch claim --issues <danh sách>`,
xử lý **hết** điểm `(blocking)`, commit vẫn mang `(#N)`, rồi `tal pr` lại. Điểm
`(non-blocking)`/`nitpick` được phép bỏ — nhưng **nói rõ bỏ cái nào và vì sao**.

---

## Khi nghi ngờ

Đọc `"$CLAUDE_PLUGIN_ROOT"/references/discipline.md` — kỷ luật "đọc ngược lại, đừng tin",
ba ca đã cắn thật, và danh sách "không bao giờ". Đừng nạp nó mỗi lượt.

## Báo cáo cuối lượt

Lô nào, gồm issue nào, PR nào, lệnh test nào + kết quả thật, issue nào bị drop và vì sao.
Kết cục âm (`drop` vì đã ship) thì nói **đã kiểm bằng cách nào**. Không kể lại từng bước.
