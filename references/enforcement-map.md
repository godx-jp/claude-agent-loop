# Luật này được cưỡng chế Ở ĐÂU, và mạnh đến đâu

Một ranh giới chỉ đáng giá bằng **chỗ nó được cưỡng chế**.

Ranh giới quan trọng nhất của vòng lặp là **tách vai**: session viết code không được review
chính nó. Đó là lý do tồn tại của cả cái vòng lặp — một agent tự chấm điểm mình thì chữ
"đạt" không mang thông tin gì. Nhưng câu đó, viết trong một skill, đã bị phá **chín lần
trong một phiên**, bởi chính session viết ra nó. Không phải vì gian: mỗi lần đều có một lý
do hợp lý tại thời điểm đó.

> **Luận điểm trung tâm của file này:** một luật chuyển từ *bị-phá-đều* sang
> *không-bao-giờ* bằng cách đổi **CHỖ nó nằm**, không phải bằng cách diễn đạt lại. Hai
> dòng trong bảng dưới đã đổi dấu đúng như vậy, và cả hai đều không đổi một chữ nào trong
> lời văn của luật.

---

## Bậc thang cưỡng chế trong plugin này

Từ mạnh xuống yếu. Khi thêm một luật, hãy leo lên bậc cao nhất mà nó chạy được.

| Bậc | Nơi | Vì sao mạnh | Giới hạn thật, nói ra chứ không giả vờ |
|---|---|---|---|
| 1 | **Hook `PreToolUse`** (`hooks/hooks.json` → `tal hook-guard`) | Chặn **trước khi** công cụ chạy. Agent không đi vòng được vì nó không phải người quyết định | Chỉ phủ lệnh đi **qua hook** của Claude Code. Người gõ tay trong terminal khác thì không |
| 2 | **Cổng trong `bin/tal`** (exit code khác 0) | Máy trạng thái + ledger nằm ở đây; mọi đường của `tal` hội tụ về vài hàm | Chỉ phủ đường đi **qua `tal`**. `gh pr merge` và nút xanh trên web đi thẳng qua (bậc 1 vá một phần) |
| 3 | **Test** (`tests/tal_test.py`) | Bắt hồi quy khi ai đó sửa `bin/tal` | Không chặn gì lúc **chạy**. Và một test khớp chuỗi trong mã nguồn thì không chặn cả lúc sửa |
| 4 | **Skill** (`skills/**/SKILL.md`) | Được nạp mỗi lượt, nên có đọc | **Chỉ là chữ.** Cái được đọc và cái được làm là hai chuyện |
| 5 | **Tài liệu** (`references/`, `docs/`) | Giải thích được thứ mã nguồn không nói | Chỉ là chữ, **và không ai đọc lúc đang làm** |

**Branch protection của GitHub đứng trên cả bậc 1** ở những luật nó phủ được (required
status checks, cấm push thẳng). Bật được thì bật — phần lớn §11 của
`references/mechanism.md` khi đó thành thừa, và đó là kết cục mong muốn. *VÍ DỤ (kho tiêu
thụ):* một repo private trên gói GitHub không hỗ trợ sẽ nhận
`403: Upgrade to GitHub Pro or make this repository public` khi hỏi endpoint protection —
đó là **giới hạn của gói**, không phải cấu hình sai, và là lý do bậc 1 và bậc 2 phải gánh.

---

## Bảng: luật → nơi cưỡng chế → mạnh đến đâu

Đọc bảng này **theo cột thứ ba**.

| Luật | Cưỡng chế ở | Mạnh đến đâu |
|---|---|---|
| Một session trên một issue | **CAS trên git ref** (`ref_create` → `POST /git/refs` trả 422 `Reference already exists`) | Tuyệt đối — lần thứ hai nhận 422 |
| Không ghi vào worktree của lô bạn không giữ | **Hook `PreToolUse`**, căn cứ từ `.tal-lease.json` | Tuyệt đối với công cụ ghi file |
| Nhánh/worktree chỉ được mang hai dạng tên (`issue-<số>`, `batch-<YYYYMMDD-HHMM>`) | **Hook `PreToolUse`**, bắt cả `git -C <path>` | Tuyệt đối |
| Không push thẳng vào nhánh base / nhánh phát hành | **Hook `PreToolUse`** (`danger_re()`, dựng từ `baseBranch` + `promotionBranch`) | Tuyệt đối — **và chỉ vì regex dựng theo config**; xem cảnh báo ngay dưới bảng |
| Không chạy full suite trong worktree của vòng lặp | **Hook `PreToolUse`** — khớp chuỗi với `fullSuite` **trừ đi** `affectedTests` | Tuyệt đối. **Dòng này từng ghi "chỉ là chữ"** |
| `gh pr merge` khi CI đỏ hoặc chưa xong | **Hook `PreToolUse`** (`GHMERGE_RE` + `pr_checks`) | Tuyệt đối **khi lệnh đi qua hook** — đây là bản vá cho đường duy nhất `tal` không phủ |
| Reviewer phải khác coder | `assert_not_own_work` ở **cả ba cửa**: `review-claim`, `review-verdict`, `merge` — exit **5** | Tuyệt đối, trừ khi người gõ `--allow-self` (review) / `--self` (merge), và cả hai **bắt buộc `--note`** ghi lên PR |
| Session thứ ba không cắt vào giữa một vòng review | `local_lock` + `ref_create` trên key `pr-<N>` — exit **75** (`BUSY`) | Tuyệt đối |
| Merge phải có verdict TRÊN GITHUB khớp HEAD | `merge_blockers` → `pr_verdict_pass_evidence` | exit 2. `--force` mở được **nhưng bắt buộc `--note`**, và note đăng lên PR |
| Merge từ chối PR có base là nhánh phát hành | `promotion_base_verdict` trong `cmd_merge` | Tuyệt đối. **`--force` KHÔNG mở** — chỉ `--promote` (một khẳng định về ý định) |
| Merge từ chối CI **đỏ** hoặc **chưa xong** | `merge_blockers` (tiền tố `CI_RED` / `CI_PENDING`) — cả đường lẻ lẫn đường lô | Tuyệt đối. **`--force` KHÔNG mở** — chỉ `--ci-red --note` |
| Lượt phát hành không được xoá file chỉ có trên nhánh phát hành | `promotion_only_files` | Tuyệt đối — **không chứng minh được thì từ chối** |
| Cổng docs chạy TRƯỚC khi nhả lease | `cmd_pr` gọi `docs_gate` rồi mới `mark_lease_released` | exit 2 và **giữ lease**. `--docs-ok` mở được, nhưng nó đăng lên PR danh sách luật đã bỏ qua |
| Mỗi commit của một lô mang đúng một `(#N)` thuộc lô | `cmd_pr` từ chối mở PR (`batch_commit_map`) | exit 2, trừ `--allow-orphan-commits` (mất khả năng `batch drop`) |
| Mỗi issue trong lô phải có commit thật | `cmd_pr` | exit 2, trừ `--allow-empty-issues` |
| Một lô không được chạm submodule | `cmd_pr` | exit 2 — submodule đi đường issue đơn, vì pointer là sha trơ nên nhánh phải mang số issue trong tên |
| Không đóng issue còn mang `status:*` khác, hoặc đã được mở lại | `closable()` + `reopened_after()` ở `cmd_merge` và `cmd_gc` | Tuyệt đối, và **fail-safe theo hướng không đụng vào issue** |
| Không xoá nhánh/worktree còn mang nội dung base chưa có | `worktree_unmerged_content()` (ba tầng, mọi đường lỗi lệch về phía GIỮ) | Tuyệt đối — `--include-abandoned` cũng không mở |
| Không dọn dẹp sau một merge chưa landed | `assert_merge_landed()`, đo bằng `git merge-base --is-ancestor` | Tuyệt đối — và SHA đọc bằng `gh_json_strict` **trước** khi merge |
| Không để lại worktree nửa-chết | `remove_worktree` (DỜI trước, XOÁ sau) + `assert_worktree_attached` | Tuyệt đối |
| Dead-letter chỉ người mở khoá được, và phải nói vì sao | `cmd_requeue` bắt buộc `--note`; `cmd_unlock` **không** reset counter | Tuyệt đối |
| "Đọc ngược lại, đừng tin" — không tin mô tả issue, không tin nhãn trên PR | `references/discipline.md` | **Chỉ là chữ.** Cố ý: nó là phán đoán, không phải một điều kiện máy kiểm được |
| Cách chạy test theo vùng, checklist review, cạm bẫy của stack | `policyDocs` của kho tiêu thụ | **Chỉ là chữ**, và đúng chỗ — nó là chính sách của repo, không phải cơ chế |

> ### Cảnh báo cho dòng "không push thẳng"
> Regex đó **phải** dựng từ config. Nó từng ghim cứng `dev|main`, nên ở mọi kho đặt tên
> nhánh khác (`trunk`, `develop`…) rào **im lặng không đóng**. Một rào im lặng không đóng
> tệ hơn không có rào: nó xuất hiện trong bảng này với chữ "Tuyệt đối" trong khi thực tế
> nó chưa từng chặn gì. Cùng bẫy đó rình ở `cmd_gc` (danh sách nhánh được bảo vệ) — chỗ
> đó "không đóng" nghĩa là `gc` **xoá nhánh chính của repo**.

---

## Hai dòng đã đổi dấu — và đó là toàn bộ luận điểm

Cả hai từng nằm ở bậc 4 (chữ trong skill). Không dòng nào được **diễn đạt lại**; chúng
được **dời chỗ**.

**1. "Không merge PR của chính mình."** Từng chỉ là chữ trong skill. Số đo: **chín lần tự
merge trong một phiên**, bởi chính session viết ra luật đó. Hôm nay
`assert_not_own_work()` so session id và exit **5** — và nó đặt ở **cả ba cửa**, vì rào cũ
chỉ đứng ở `review-claim`, trong khi `review-verdict` mới là chỗ **sinh ra hệ quả** (nó
gắn nhãn quyết định merge) và `merge` là chỗ hệ quả **thành thật**. Chặn một cửa thì hai
cửa kia vẫn mở, và cả hai đều đã bị đi qua.

**2. "Chỉ chạy test hẹp, không chạy full suite."** Cũng từng chỉ là chữ. Ruling gỡ full
suite khỏi đường tự động chỉ chặn **đường tự động** — không có gì ngăn một session tự gõ
lệnh full suite trong worktree và trả lại đúng 9–10 phút mỗi lần. Hôm nay `hook-guard`
**deny** mọi lệnh chứa một chuỗi khai trong `fullSuite`.

Danh sách chặn là `fullSuite` **TRỪ ĐI** `affectedTests` (`banned_in_worktree()`), nên một
lệnh nằm ở cả hai chỗ vẫn chạy được. Chi tiết đó không phải sự tiện lợi: **rào không được
tự chặn đúng cái đối chứng mà chính nó bảo agent phải dùng.** Một rào chặn cả đường thoát
sẽ bị tắt, không bị tranh luận.

Cùng bài học ở một chỗ thứ ba: `strip_heredocs()` bóc thân heredoc trước khi khớp mẫu —
vì một commit **mô tả** rào (trích một lệnh push-thẳng để giải thích nó chặn cái gì) từng
bị chính nó từ chối. **Rào báo oan thì bị TẮT.**

---

## Thủ tục: thêm một luật mới

Câu hỏi đầu tiên là **"nó được cưỡng chế ở đâu"**, không phải "diễn đạt thế nào".

Một luật đặt ở chỗ chỉ thiện chí đọc tới thì sẽ bị phá. Một luật đặt ở chỗ máy **buộc phải
đi qua** thì không.

### 1. Nó là CƠ CHẾ hay CHÍNH SÁCH?

Áp câu hỏi cho **từng đoạn**, không áp cho cả file:

> **Câu này còn đúng ở một kho stack khác không?**

- **Đúng** ⇒ thuộc **plugin**: `bin/tal`, `hooks/`, `skills/`, `references/`.
- **Không** ⇒ ở lại kho tiêu thụ, dưới dạng **config** (`affectedTests`, `fullSuite`,
  `docsRules`, `labels`, `policyDocs`…) hoặc một policy doc đã thu gọn.

Sai chiều nào cũng hỏng, và **chiều kéo-phần-riêng-vào-plugin tệ hơn**: nó mang giả định
của một kho sang mọi kho khác, và biểu hiện là một rào im lặng không đóng.

Nếu câu trả lời là "thuộc plugin" mà plugin **chưa có bề mặt** để nhận, thì thêm bề mặt
đó — đừng ép nhét vào một khoá sai nghĩa.

### 2. Leo lên bậc cao nhất mà nó chạy được

Đi từ trên xuống bảng bậc thang:

- Chặn được **trước khi công cụ chạy**, chỉ bằng cách đọc chuỗi lệnh hoặc đường dẫn?
  → **hook `PreToolUse`**.
- Cần đọc trạng thái GitHub (nhãn, verdict, check, ledger)? → **cổng trong `bin/tal`**,
  exit code khác 0.
- Là một phán đoán con người phải làm ("bản sửa này có đúng nguyên nhân gốc không")?
  → **skill**, và chấp nhận rằng nó chỉ là chữ. **Đừng giả vờ** một luật ở bậc 4 là
  "tuyệt đối" trong bảng.

Chỉ dừng ở bậc thấp khi bậc cao **thật sự không chạy được**, và hãy viết ra lý do.

### 3. Chọn chiều hỏng, và nói to

Mọi rào đều sẽ gặp ca "không đo được". Quyết định chiều **trước**, đừng để nó rơi ra từ
cách viết code:

- **Fail-closed** khi hỏng nghĩa là mất thứ không lấy lại được: giữ worktree, không đóng
  issue, không xoá nhánh, không stamp nhãn.
- **Fail-open** khi fail-closed sẽ chặn mọi thứ và vì thế bị gỡ nguyên khối: đọc không
  được `baseRefName` thì cho merge qua, vì cổng đó canh một tai nạn cụ thể chứ không canh
  mạng chập chờn.

Và ở mọi phép đo dẫn tới một **quyết định phá huỷ**, "không đo được" phải **RAISE**, không
được trả rỗng — dùng `gh_json_strict` / `gh_json_required`, không dùng `gh_json`. Một 502
trả `""` biến "API hỏng" thành "đo xong, không có gì".

### 4. Đặt cửa thoát cho đúng chỗ, và bắt nó để lại dấu vết

- Cờ bỏ qua phải **hẹp** và **có tên riêng**. `--force` là thứ mọi session gõ hằng ngày;
  một rào mà `--force` mở được là rào chết ngày đầu. Vì thế `--promote`, `--ci-red`,
  `--force-region`, `--self` là những cờ **riêng biệt** — mỗi cái là một khẳng định về ý
  định, không phải một cách nói "kệ đi".
- Cửa thoát phải **đắt và để lại dấu vết**: `--note` bắt buộc, và lời khẳng định đăng
  thẳng lên PR. **Một cờ bỏ qua mà im lặng chỉ là cái cổng đã tắt.**

### 5. Viết test lái LỆNH, không khớp chuỗi trong mã nguồn

Đây là bài học đắt nhất trong repo này. Một test khẳng định `worktree_unmerged_content(`
xuất hiện trong `cmd_gc` vẫn **xanh** khi rào bị tắt bằng `if False and …`. Rào tắt hoàn
toàn, 138 test xanh, không ai nhận ra.

Test phải:

- chạy **lệnh thật** (`cmd_gc`, `cmd_merge`, `hook-guard` với payload thật);
- khẳng định **hệ quả** đã hoặc chưa xảy ra (`DELETE refs/heads/` chưa từng được phát;
  worktree/branch/ledger còn nguyên);
- và có **chiều ngược**: tiêm lỗi để chắc rào **thật sự bắt**. Một rào chưa bao giờ chạy
  đỏ là một rào chưa biết có chạy hay không.

Ghim luôn cả **chỗ nối**, không chỉ helper: xoá một lời gọi khỏi `cmd_merge` vẫn để toàn
bộ test của helper xanh.

### 6. Ghi lý lẽ vào đúng chỗ

- **Vì sao rào tồn tại, và điều gì hỏng nếu gỡ nó** → `references/mechanism.md`, kèm bằng
  chứng đo được (ngày, số hiệu issue của kho tiêu thụ, con số).
- **Rào này nằm ở bậc nào** → thêm một dòng vào bảng trên. Nếu bậc đổi, hãy nói **nó đã ở
  đâu trước đó và điều gì đã xảy ra ở đó** — đó là thứ làm bảng này thuyết phục.
- **Cách thoát khi gặp rào lúc vận hành** → `references/runbook.md`.
- **Điều session phải làm mỗi lượt** → `skills/`, ngắn nhất có thể.

### 7. Phép thử cuối: rào có CHẠY TỚI ĐƯỢC không

Đo bằng **payload thật**, đừng tin comment. Đã có **năm** lần cùng một hình dạng trong
repo này: một rào viết đúng, nằm sau một điều kiện làm nó không bao giờ chạy tới. Ca gần
nhất — hai phép kiểm nằm trong nhánh "chỉ chạy trong worktree" trong khi comment ngay trên
chúng khẳng định "vẫn áp cho mọi lệnh Bash như cũ"; đo bằng payload thật từ gốc repo:
`git push origin <base>` exit 0, không chặn.

**Rào đúng mà không bao giờ chạy tới thì bằng không** — và tệ hơn không, vì nó chiếm một
dòng "Tuyệt đối" trong bảng ở trên.
