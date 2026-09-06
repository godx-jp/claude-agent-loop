# Vì sao `tal` hành xử thế này — đọc TRƯỚC khi sửa `bin/tal`

File này viết cho **người sắp sửa công cụ**, không phải cho session đang chạy vòng lặp.
Session đọc `skills/`; người vận hành đọc `references/runbook.md`; người sửa `bin/tal`
đọc chỗ này.

`bin/tal` gần 7.700 dòng, và phần lớn độ dài ấy là **rào**. Mỗi cái rào trông như một
nhánh `if` thừa cho tới lúc bạn biết nó chặn cái gì. Không có file này thì người sửa kế
tiếp sẽ gỡ đúng những cái đã trả giá — vì đọc mã nguồn ra "phòng thủ quá tay", chứ không
ra "đã cắn thật ngày 16/08".

Mỗi mục dưới đây có đúng ba phần: **hành vi hiện tại → vì sao → điều gì hỏng nếu gỡ nó.**

---

## Cách đọc file này

**Số hiệu `#NNNN`.** Mọi số hiệu issue trong file này (và trong comment của `bin/tal`)
là issue của **kho tiêu thụ `godx-jp/godx-tempo`** — nơi các sự cố được đo và ghi lại.
Chúng là **dấu vết lịch sử**, giữ để tra ngược, KHÔNG phải issue của repo plugin này.

**Tên nhánh.** File này không bao giờ viết `dev` hay `main` như một sự thật. Vòng lặp
biết hai nhánh, cả hai đều là **cấu hình của repo tiêu thụ**:

| Trong tài liệu | Hằng số trong `bin/tal` | Khoá config | Mặc định |
|---|---|---|---|
| *nhánh base* | `BASE_BRANCH` | `baseBranch` | `dev` |
| *nhánh phát hành* | `PROMOTION_BRANCH` | `promotionBranch` (đọc cả `mainBranch`) | `main` |

Đây không phải cầu kỳ về chữ nghĩa. Đã trả giá đúng chỗ này: `DANGER_RE` từng ghim cứng
`dev|main`, nên rào chặn push-thẳng **im lặng không đóng** ở mọi kho đặt tên nhánh khác
(`trunk`, `develop`…). Hôm nay nó là `danger_re()` — một hàm dựng regex từ `BASE_BRANCH`
và `PROMOTION_BRANCH` — và docstring của nó nói thẳng lý do. Một rào im lặng không đóng
tệ hơn không có rào. **Mọi hằng số bạn thêm vào phải qua config, không qua literal.**

**Lệnh test, đường dẫn, tên stack.** Không có cái nào thuộc plugin. `affectedTests`,
`fullSuite`, `setup`, `setupVerify`, `docsRules` đều là khoá config. Ở đâu file này cần
một ví dụ cụ thể, nó được dán nhãn *VÍ DỤ (kho tiêu thụ)* — đừng chép nó vào `bin/tal`.

---

## 1. Fencing — chỗ dễ tưởng là đã an toàn nhất

**Hành vi.** Loại trừ tương hỗ là **lease** (Gray & Cheriton) trên một primitive CAS
thật: `POST /git/refs` trả 422 `Reference already exists` nếu ref đã tồn tại. Liveness
là **visibility timeout** kiểu SQS: TTL (`ttlSeconds`, mặc định 45 phút) + heartbeat,
đo bằng `updated_at` của ledger comment — **đồng hồ SERVER**, miễn nhiễm clock skew trên
máy giữ lease. Trên đó là **fencing token** (Kleppmann): mỗi lần cấp lại lease thì
`epoch` tăng đơn điệu; `do_assert()` từ chối khi epoch của thẻ khác epoch của sổ (exit
`4`); mọi push đi qua `push_with_lease()` với `--force-with-lease=<branch>:<sha-vừa-đọc>`.

**Vì sao.** TTL một mình KHÔNG chặn được ca này: một session treo 50 phút (máy ngủ,
GC stop-the-world, mạng nghẽn), lease hết hạn, session khác nhận issue, rồi session cũ
tỉnh dậy và `git push` như không có gì xảy ra. Đó chính là lỗ hổng Kleppmann chỉ ra ở
mọi thiết kế chỉ-có-TTL. Nên đường ra remote bị chặn **hai lớp**: `tal assert` (hook gọi
trước mỗi `git push` / `gh pr create`) và `--force-with-lease` ở tầng git.

`push_with_lease()` ghim **giá trị**, không tin remote-tracking ref: `git fetch --prune
origin` chạy ở mọi lần claim và làm tươi ref cho TẤT CẢ branch, nên `--force-with-lease`
trần thoái hoá thành `--force` — một commit người khác vừa push lên `origin/issue-N` bị
đè không một lời. `ls-remote` hỏng ⇒ expect-trống, push fail nếu branch tồn tại (hướng
an toàn).

**Gỡ thì hỏng gì.** Bỏ `epoch` ⇒ mất chính thứ TTL không làm được. Đổi `push_with_lease`
về `--force-with-lease` trần ⇒ rào vẫn còn, vẫn xanh, và im lặng không chặn gì.

### 1b. Nhả lease là ĐÁNH DẤU thẻ, KHÔNG xoá nó

**Hành vi.** `mark_lease_released(wt)` ghi `released: true` + `released_at` vào
`.tal-lease.json`, **bỏ `epoch`**, và ghi **nguyên tử** (`tmp` + `os.replace`). Thẻ ở
lại trên đĩa. Hệ quả dây chuyền, cả ba đều có chủ ý:

- `hook-guard` lấy căn cứ từ chính thẻ đó ⇒ nó **chặn tất cả**, kể cả chủ cũ, kèm thông
  điệp chỉ đúng `tal claim <N>`;
- `do_assert()` báo `LEASE ĐÃ NHẢ` (exit 4) thay vì đi tiếp;
- `lease_file(search=True)` **bỏ qua** thẻ đã released khi quét worktree của chính
  session này, nên lỗi "session này đang giữ nhiều worktree" không tái diễn.

**Vì sao.** `tal pr` và `tal release` GIỮ LẠI worktree cho vòng sửa sau. Nếu nhả lease
mà xoá thẻ thì worktree ấy **không còn ai canh**, và WIP của session khác trôi vào —
đã xảy ra ở `.claude/worktrees/issue-1306`: 5 file WIP không thuộc session tạo ra nó,
giống hệt từng byte với WIP ở worktree gốc. Bỏ `epoch` vì giữ fencing token của một
lease đã hết hiệu lực chỉ tạo ảo giác còn quyền ghi.

**Gỡ thì hỏng gì.** `f.unlink()` thay cho đánh dấu = tháo `hook-guard` khỏi worktree đó.
Nhánh `except` khi thẻ hỏng cũng phải **ghi đè**, không được unlink, vì cùng một lý do
— đó là lỗi 4 của #1342. Và ghi không nguyên tử thì một lần bị kill giữa chừng để lại
JSON hỏng, lần sau rơi vào nhánh except.

### 1c. Mất THẺ không phải mất LEASE — `tal adopt`

**Hành vi.** Thẻ trên đĩa là **cache**. Quyền sở hữu sống ở hai chỗ có thẩm quyền, cả hai
trên server: ref CAS `<refNamespace><key>` và ledger comment. `tal adopt [<issue>]` dựng
lại `.tal-lease.json` từ sổ, **GIỮ NGUYÊN epoch**, không cấp thêm quyền gì.

> **Đính chính so với tài liệu cũ ở kho tiêu thụ.** Tài liệu godx-tempo ghi *"`tal adopt`
> đã bị GỠ trong bản viết lại theo lô"*. Sai với `bin/tal` của plugin: `cmd_adopt` còn
> nguyên và `tal adopt --help` chạy. Thông điệp lỗi của `lease_file()` cũng trỏ thẳng
> vào nó.

**Vì sao.** Không có `adopt` thì mất thẻ trong khi lease vẫn sống chỉ còn hai lối ra
chính thức, và **cả hai đều phá một thứ**:

| Lối ra | Cái giá |
|---|---|
| `tal claim <n>` lại | **bump `epoch`** — đúng cái fencing token sinh ra để ngăn |
| `tal unlock <key> --force` | **vứt một lease đang sống**, mở issue cho session khác |

Đã xảy ra thật: một `git worktree prune` giữa chừng làm mất đăng ký worktree, thẻ đi
theo, và thẻ phải được **gõ tay lại** từ ledger đọc trên GitHub.

**Gỡ thì hỏng gì.** Thông điệp "không thấy thẻ" mà không nêu đường phục hồi sẽ đẩy người
đọc về lối thoát gần nhất là `claim` lại — tức bump epoch. Thông điệp và lệnh là một cặp;
gỡ lệnh mà giữ thông điệp là để lại một lời khuyên trỏ vào hư không.

---

## 2. Máy trạng thái, và `closable()` — hai lần từ chối đóng issue

```
     người gắn nhãn ready
              │
              ▼
        (hàng đợi)  ◄────────────────────────────┐
              │ tal batch claim → lease + worktree│ lease hết hạn → tal gc thu hồi
              ▼                                   │
      status:executing ──────────────────────────┘
              │ tal pr → PR vào base, rồi CỔNG DOCS, rồi mới nhả lease
              ▼
  status:reviewing + agent:awaiting-review
              │ tal review-claim (BẮT BUỘC là session khác)
              ▼
      ┌───────┴────────┐
      ▼                ▼
agent:changes-      agent:review-passed
 requested            │
 (ƯU TIÊN #1)         ▼
      │        tal merge-batch: trộn CẢ LÔ lên base trong cây tạm
      │          → full suite MỘT lần → xanh thì merge cả lô
      └──► quay lại claim  │
           (tối đa 3 vòng) ▼
                     tal merge → status:shipped + ĐÓNG issue
                     tal gc    → xoá branch và worktree
```

**Hành vi.** Merge vào nhánh base thì `tal` tự đóng issue. `closable(n, merged_at)` từ
chối hai ca:

1. issue còn mang **một nhãn `status:*` khác** `shipped`;
2. issue đã **được MỞ LẠI** sau `mergedAt` (`reopened_after()`).

**Vì sao (1).** `Closes #N` mà `tal pr` chèn vào thân PR **không bao giờ chạy** ở luồng
này: GitHub chỉ auto-close khi PR merge vào **default branch** của repo, mà vòng lặp
luôn nhắm nhánh base — thường không phải default. Trước khi có lệnh đóng, issue nằm ở
`OPEN + status:shipped` vô hạn (22 cái phải dọn tay trong một ngày). Nhưng `tal merge`
gắn `status:shipped` cho **MỌI** PR merge, kể cả PR mới xong một pha của một epic:
*VÍ DỤ (kho tiêu thụ)* — #962 mang cả `status:planning`, #1392 mang cả `status:blocked`.
Đóng chúng là **xoá việc dang dở khỏi tầm mắt**.

**Vì sao (2).** Nhãn `status:*` KHÔNG bắt được ca thứ hai: issue vừa mở lại thường mang
`agent:ready`, không mang `status:` nào. Hình dạng này lặp **bốn lần trong một phiên**:
một PR làm xong MỘT PHẦN, `Closes #N` đóng nó, người mở lại kèm comment liệt kê phần còn
lại — rồi `gc` đóng lại trong vòng 5 phút. Việc biến mất khỏi `tal queue`, im lặng.

`reopened_after()` **fail-safe theo hướng KHÔNG đụng vào issue**: timeline không đọc
được, JSON hỏng, `--paginate` trả nhiều mảng nối nhau ⇒ trả `True` (coi như đã reopen).
Đóng nhầm là mất việc; bỏ qua nhầm chỉ là một dòng nhãn cũ.

**Gỡ thì hỏng gì.** Bỏ (1) ⇒ epic bị đóng giữa chừng. Bỏ (2) ⇒ mọi quyết định "mở lại vì
còn thiếu" bị `gc` xoá trong 5 phút. Đảo chiều fail-safe của `reopened_after` ⇒ một lỗi
API biến thành một lần đóng nhầm.

### 2b. `gc` phải hỏi `closable()` TRƯỚC khi đụng vào nhãn

**Hành vi.** Trong `cmd_gc`, **gắn nhãn** và **đóng** chịu CHUNG một điều kiện: hỏi
`closable()` cho từng issue trong nhóm trước, rồi mới ghi.

**Vì sao.** Bản cũ gắn nhãn vô điều kiện rồi mới hỏi `closable()` để quyết định đóng,
nên `gc` tự mâu thuẫn trong cùng một lần chạy: in *"KHÔNG đóng #962: còn mang
status:planning"* ngay sau khi vừa gắn `status:shipped` cho chính nó. Issue mang cả hai
nhãn, và `tal queue` lọc theo nhãn — nên nó **rơi khỏi hàng đợi**.

**Gỡ thì hỏng gì.** Tách hai điều kiện ra lần nữa ⇒ đúng lỗi cũ, và nó không hiện ra
dưới dạng lỗi: chỉ là một issue lặng lẽ biến mất khỏi backlog.

---

## 3. Dọn dẹp sau merge gác trên một PHÉP ĐO, không gác trên exit code

**Hành vi.** `cmd_merge` làm ba việc **không rollback được** ngay sau khi `gh pr merge`
trả 0: xoá worktree, **xoá nhánh remote**, ghi ledger `shipped`. Giữa merge và dọn có
`assert_merge_landed(pr, head_sha)`: fetch nhánh base rồi đòi
`git merge-base --is-ancestor <head> origin/<base>`. Không phải tổ tiên ⇒ `Fail`, và
worktree / nhánh / sổ **giữ nguyên**.

**Vì sao.** Exit 0 KHÔNG có nghĩa commit đã vào base. Hình dạng thật sự xảy ra là
`Base branch was modified`: GitHub nhận lệnh, base dịch bên dưới, không có gì landed.
Ngày 16/08 một issue mất cả hai PR lẫn nhánh trong khi nhánh base vẫn mang bản chưa vá.
Xoá nhánh là việc đắt nhất: `gh pr reopen` cần head branch còn sống, nên một khi nhánh
đi rồi thì PR không mở lại được và việc chỉ còn trong worktree cục bộ — thứ mà `tal gc`
được phép quét.

Bốn chi tiết đều chịu lực, đừng đụng cái nào một mình:

| Chi tiết | Vì sao |
|---|---|
| head SHA đọc **TRƯỚC** khi merge | Sau đó nhánh có thể đã mất, không còn gì để hỏi |
| Đọc bằng `gh_json_strict`, hỏng thì `Fail` **TRƯỚC** cả `gh pr merge` | Docstring của `gh_json` cấm đúng chuyện này: *"đường nào dùng kết quả để QUYẾT ĐỊNH PHÁ HUỶ phải đi `gh_json_strict`/`gh_json_required`"*. Với `gh_json`, một cú 502 trả `""`, rào không có gì để so và im lặng cho qua — API hỏng biến thành "đo xong, không có gì". Fail trước merge cũng sạch hơn fail sau: chưa merge thì chưa có gì phải undo |
| Helper vẫn **im khi `head_sha` rỗng** | Phòng thủ cho người gọi khác, không phải đường của `cmd_merge` (chỗ đó đã `Fail` từ trước). Một hàm đo mà tự nổ khi thiếu đầu vào sẽ bị người gọi kế tiếp bọc `try/except` — và một rào bị bọc `try/except` là rào đã tắt |
| Phép đo gắn với `--merge` | Merge commit giữ head làm tổ tiên. Đổi sang `--squash` thì nội dung vào base dưới SHA khác và rào kêu oan mọi lượt. `test_merge_uses_merge_commit_so_ancestry_holds` ghim cặp đôi đó lại |

**Chỗ GỌI cũng được ghim, không chỉ helper.** Tách phép kiểm ra làm nó test được, nhưng
cũng biến chỗ nối thành nơi không ai canh: xoá `assert_merge_landed(...)` khỏi `cmd_merge`
vẫn để toàn bộ test của helper xanh. Có một test lái **lệnh thật** và khẳng định ba hệ
quả không-rollback-được đã KHÔNG xảy ra.

**Gỡ thì hỏng gì.** Đổi `gh_json_strict` về `gh_json` ⇒ cleanup phá huỷ chạy y như trước
bản vá, không ai thấy. Đổi merge method mà quên rào ⇒ mọi merge bị từ chối, rào bị gỡ
"vì nó hỏng". Xoá lời gọi mà giữ helper ⇒ 149 test vẫn xanh.

Cùng bài học một tầng phía trên: **một trạng thái nói "xong" không phải bằng chứng có
thứ gì đã landed — phải đo nội dung.**

---

## 4. `gc --include-abandoned` hỏi về thứ SẮP MẤT

**Hành vi.** `gc` coi "PR đóng mà không merge" là "việc bị bỏ", và với
`--include-abandoned` sẽ xoá cả nhánh remote lẫn worktree. Trước khi xoá, nó **đo**:
`worktree_unmerged_content(..., rev=f"origin/{branch}")` sau khi fetch nhánh về. Còn
nội dung ⇒ **TỪ CHỐI**, kèm câu lệnh để người đọc tự xem nhánh còn giữ gì.

**Vì sao.** "PR đóng không merge ⇒ việc bị bỏ" là một **suy luận từ trạng thái**, và tiền
đề sai ba lần trong hai giờ ngày 16/08: ba issue đều `mergedAt=null` trong khi mang việc
đã xong, đã test, chưa vào base. Một cái sống sót CHỈ vì worktree cục bộ còn — đúng thứ
đường này được phép dọn.

**Hỏi về VẬT SẮP MẤT.** Bản sửa đầu tiên đo **worktree**, trong khi lệnh xoá một **ref
remote**. Hai vật khác nhau: worktree sạch bên cạnh một ref còn mang commit là chuyện
thường (reset, hoặc push xong rồi dọn), và trên máy KHÔNG có worktree thì phép đo cũ
không đo được gì cả rồi xoá. Đó không phải ca hiếm — chính `gc` là thứ dọn worktree đi,
nên **mọi lượt sau lần đầu** đều rơi vào đó. Nên helper nhận tham số `rev`, và đường này
hỏi `origin/<branch>`; worktree chỉ là phương án dự phòng khi ref remote đã mất.

**Dùng lại `worktree_unmerged_content`, không đo mới.** Helper đó đã qua hai vòng sửa
(#2300 A12 → #2674) và hiểu cả ca squash. Hai rào trả lời cùng một câu hỏi bằng hai phép
đo khác nhau thì sẽ trôi khỏi nhau.

**Và test phải lái LỆNH, không khớp chuỗi trong mã nguồn.** Bản đầu khẳng định chuỗi
`worktree_unmerged_content(` có mặt trong `cmd_gc`. Tắt rào bằng `if False and …` vẫn để
chuỗi đó nguyên chỗ và cả bộ test xanh — rào tắt hoàn toàn, không ai nhận ra. Test hiện
tại chạy `cmd_gc` thật và khẳng định `DELETE refs/heads/` chưa từng được phát, ở cả hai
hình dạng: có worktree và không có.

**Gỡ thì hỏng gì.** `--include-abandoned` giữ nghĩa "tôi biết đây là việc bỏ" cho một
nhánh không mang gì base chưa có. Cho nó xoá một nhánh **có** mang thì việc mất đi như
một tác dụng phụ của một lượt dọn rác.

---

## 5. `tal pr` chạy cổng docs TRƯỚC khi nhả lease

**Hành vi.** `cmd_pr` mở/cập nhật PR → đánh giá `docs_gate(pr)` → **rồi mới**
`mark_lease_released(wt)`. Có khoảng trống ⇒ `Fail`, **lease vẫn giữ**, sửa ngay trong
cùng lượt (PR cập nhật tại chỗ ở lần chạy sau).

**Vì sao.** Thứ tự cũ mà skill kê ra là `tal pr` rồi `tal docs-check <PR>` — và nó
**không chạy được**. `tal pr` nhả lease ngay khi PR mở, nên tới lúc `docs-check` báo
thiếu thì worktree đã bị hook chặn ghi:

```
[tal] LEASE ĐÃ NHẢ: worktree này thuộc issue #… — Ghi vào đây bây giờ là ghi ra ngoài mọi rào.
```

Claim lại cũng không được (issue đã mất nhãn ready), nên đường duy nhất để sửa tài liệu
trong cùng lượt là `tal claim --force` — bước vòng qua một cổng **đang chặn**. Đó là
điều cấm. Kết quả thật: **mọi** phát hiện của docs-check phải đi qua trọn một vòng
review, kể cả khi nó là một đoạn văn thêm vào một file `.md`.

**Chỉ `docsRules` giữ lease.** `docsGenericRules` (mặc định **rỗng**, có chủ ý) là gợi ý
cho người review, không phải cổng. Luật kiểu "chạm route thì phải regen tài liệu API" nói
về **cây thư mục của một repo cụ thể**; mang nó sang repo khác là phát biểu sai — và
biến một phát biểu sai thành cổng thì dạy người ta đi vòng qua cổng.

**`--docs-ok` là một KHẲNG ĐỊNH, không phải nút tắt.** Nó nhả lease *và* đăng comment lên
PR nêu tên từng luật đã bỏ qua, để người review đọc được lời khẳng định và bác nếu sai.
Một cờ bỏ qua mà im lặng chỉ là cái cổng đã tắt.

**`cmd_docs_check` và cổng dùng CHUNG một hàm** (`docs_gate`). Hai bộ đếm độc lập sẽ trôi
lệch, và lúc đó câu "docs-check đã xanh" không còn nghĩa gì — xanh ở phép đo nào?

### 5b. `pr_files()` phân trang và FAIL CLOSED

**Hành vi.** Cả hai người gọi lấy danh sách file qua `GET /pulls/{n}/files` với
`--paginate`, rồi **đối chiếu số lượng nhận được với `changed_files`** — một phép đo độc
lập từ chính PR. Lệch ⇒ `DocsFilesUnavailable`. `tal docs-check` exit khác 0; `tal pr`
**giữ lease** và bảo chạy lại; lối ra duy nhất vẫn là `--docs-ok`, và nó đăng comment
`docs-unchecked` nói rõ cổng đã KHÔNG chạy.

**Vì sao.** `gh pr diff --name-only` dùng endpoint diff chung và GitHub từ chối diff quá
lớn. Không có phép đối chiếu, một lỗi API / một trang thiếu / trần 3.000 file trở thành
**danh sách rỗng**, và `docs_gate` trên danh sách rỗng thì mọi luật `docsRules` im lặng
không chạy — vẫn exit 0, vẫn "xanh".

**Gỡ thì hỏng gì.** Bỏ đối chiếu `changed_files` ⇒ PR càng lớn (tức càng đáng kiểm) thì
cổng càng chắc chắn không chạy. Cho `--docs-ok` im lặng ⇒ mất luôn dấu vết để reviewer
biết đã có gì bị bỏ qua.

---

## 6. Dọn rác: hỏi NỘI DUNG, không hỏi quan hệ tổ tiên

**Hành vi.** `worktree_unmerged_content(wt, base, merged_head_sha=None, rev="HEAD")` trả
lý do (chuỗi) khi `rev` **CÒN** giữ nội dung mà `origin/<base>` chưa có, `None` khi không
còn gì để mất. Ba tầng, mọi đường lỗi lệch về phía **GIỮ**:

0. **`merged_head_sha` khớp tuyệt đối HEAD ⇒ nhả ngay** (#2792). Câu hỏi rẻ nhất và chắc
   nhất, hỏi trước mọi phép so nội dung.
1. `git cherry origin/<base> <rev>` — dòng `-` nghĩa là patch đó đã ở upstream, bất kể
   SHA. Bắt trọn ca squash một-commit.
2. Còn dòng `+` ⇒ hỏi **CÓ CHIỀU**: HEAD có dòng nào `origin/<base>` chưa có không
   (`git diff --numstat`, cột added). `added > 0` ⇒ giữ.

**Vì sao tầng 0.** Repo squash-merge thì `git cherry` không bao giờ rỗng, và phép so nội
dung ở tầng 2 chỉ nhả khi MỌI file worktree chạm còn byte-identical với base — hỏng ngay
lần đầu có người sửa tiếp bất kỳ file nào trong số đó. Cửa sổ dọn được vì thế hẹp bằng
khoảng tới lần sửa kế tiếp, và ngoài cửa sổ đó worktree bị giữ **vĩnh viễn**, kèm một
dòng cảnh báo đọc như "có người đang làm dở" về việc đã ship xong. Chỉ nhả khi **khớp
tuyệt đối**: merged mà HEAD có commit thêm sau đó thì phần thêm chưa ở đâu cả.

**Vì sao tầng 1.** Phép đo cũ là `git log origin/<base>..HEAD` — tức **quan hệ tổ tiên
theo SHA**. Repo squash-merge thì commit của nhánh bị viết lại thành commit MỚI với SHA
khác, nên commit cũ **không bao giờ** là tổ tiên của base. Vòng lặp gọi hàm này chỉ duyệt
PR **đã merge**, nên rào cũ bắn trúng **100%** số worktree nó gặp: chưa từng nhả được
cái nào. Sáu worktree tích lại, mỗi cái mang nguyên một lượt `setup`.

**Vì sao `added == 0` chưa đủ để nhả.** Commit **chỉ xoá** (`git rm`, gỡ dòng chết) cũng
ra `added == 0`, mà `deleted > 0` của một diff hai điểm thì **mù chiều**: nó vừa có thể
là "HEAD xoá mà base chưa nhận" (mất việc thật nếu nhả), vừa có thể là "base đi tiếp,
worktree chỉ TỤT" (phải nhả). Phân xử bằng **merge-base**:
`git diff --numstat <merge-base> HEAD -- <file>` đo thứ CHÍNH HEAD làm từ điểm rẽ nhánh.
HEAD không xoá gì ⇒ nhả; HEAD tự tay xoá ⇒ **giữ** (fail-closed). Binary / không đọc
được ⇒ giữ.

Cả ba tầng đều chịu lực và mỗi tầng có ca riêng trong bộ test. **Giữ nhầm tốn đĩa; nhả
nhầm là `branch -D` nuốt bản sao cuối cùng của một commit xoá-mã.**

### 6b. `cmd_gc` fetch nhánh base TRƯỚC khi đo

**Hành vi.** Dòng đầu tiên của `cmd_gc` là `git fetch -q origin <BASE_BRANCH>`
(`check=False` — mất mạng thì gc vẫn chạy, bảo thủ).

**Vì sao.** Không có nó, `refs/remotes/origin/<base>` cũ bằng đúng lần fetch gần nhất:
một PR vừa merge trên remote trông như việc chưa push, và dòng bỏ qua đọc như thể có
commit sắp mất.

### 6c. `remove_worktree` từ chối CÂY CHÍNH, và không bao giờ khai thành công hộ

**Hành vi.** `worktree_paths_for_issue()` tra qua `git worktree list`, không chỉ đoán
`<worktrees_dir>/issue-N`. Trước **mọi** hành động, nếu đường dẫn giải ra trùng
`C.main_worktree` thì in cảnh báo và `return False`. Cuối hàm, `git branch -D` thất bại
hoặc còn worktree sót ⇒ cảnh báo + `return False` — **gc không được khai đã xoá thứ nó
chưa xoá**.

**Vì sao.** Hỏi `git worktree list` có một cạnh sắc: khi nhánh `issue-N` đang checkout ở
**cây chính** — hook ép mọi nhánh phải mang tên đó, và làm việc thẳng trong umbrella là
chuyện xảy ra — thì chính cây chính lọt vào danh sách. `git worktree remove --force` từ
chối nó ("is a main working tree"), **nhưng nhánh orphan-fallback thì không hỏi lại**:
không có rào, nó đổi tên cả repo thành `<tên>.orphan-<ts>` rồi xoá — mất mọi nhánh cục
bộ và cả sổ đăng ký worktree.

**Gỡ thì hỏng gì.** Bỏ rào cây chính ⇒ một lượt `tal gc` bình thường xoá repo. Cho
`remove_worktree` trả `True` khi chưa xoá xong ⇒ `gc` in "đã xoá worktree + branch" **mỗi
lần chạy**, mãi không hội tụ.

### 6d. `reap_leases` — thu hồi mà không làm issue rơi khỏi cả hai hàng đợi

**Hành vi.** Thu hồi lease im lặng quá TTL (theo đồng hồ server). Với key `pr-<N>` nó
**hỏi trạng thái PR trước khi re-stamp nhãn**: merged ⇒ không stamp; đóng-không-merge ⇒
trả issue về hàng đợi code; đang mở ⇒ về hàng đợi review; **không đo được ⇒ không stamp
gì cả**, chờ lượt sau.

**Vì sao.** Bản cũ `set_state_labels(…, set())` tháo hết nhãn làm việc và để issue ở
**không hàng đợi nào**. Còn re-stamp mù thì dán `{reviewing, awaiting-review}` lên một
issue **đã ship**, kẹt "đang chờ review" vĩnh viễn.

Ba nhánh phòng thủ khác trong cùng hàm, đều là "không đo được ≠ không còn":
- `pr_issue()` ném `Gone` (404 THẬT) thì mới xoá ref; ném `Fail` (quota cạn, mạng) thì
  **để nguyên** — quota cạn từng làm `gc` xoá ref lease review đang sống, rồi hai session
  review chồng nhau;
- ref của **thành viên nhóm** không có sổ riêng (ledger chỉ ghi ở root) — trước đây bị coi
  là mồ côi và xoá TRONG KHI lease nhóm còn sống;
- có ref mà chưa có sổ ⇒ đi qua `orphan_ref_is_stale()`, không xoá thẳng.

`stranded_review_candidates()` là mảnh ghép còn lại: `tal gc` và `tal status` cùng quét
cặp đã mắc kẹt (PR `issue-N` mở, issue thiếu nhãn review/ready) và dán lại — đó là cách
những ca cũ được nhặt lên mà không phải viết lại lịch sử ledger bằng tay.

---

## 7. Issue mà bản sửa đã nằm trong một PR MỞ thì rời hàng đợi — trừ `changes-requested`

**Hành vi.** `queue_skip_reason` gọi `issues_claimed_by_open_prs()` (issue → số PR mở
đang khai `Closes` nó) và bỏ issue đó khỏi hàng đợi, **trừ khi** issue mang nhãn
`changesRequested`.

**Vì sao rào này tồn tại.** `tal claim` giữ lease trên **một** issue, nhưng một **PR cụm**
đóng nhiều issue. N−1 issue còn lại giữ nguyên `agent:ready` và quay lại `eligible` ngay
khi PR mở. Không có gì sai với nhãn nào cả — nhãn cho những issue đó **không bao giờ được
ghi**, nên chờ nó là chờ một thứ không tới. Hai phép kiểm tiêu chuẩn đều hụt:
`git log --grep="#N"` không thấy (commit trên nhánh chưa merge), `gh pr list --search`
theo tên nhánh cũng không thấy (PR cụm mang tên nhánh của issue **chính**). Thân PR là
chỗ duy nhất ghi đủ cả nhóm, và `tal pr` đã tự chèn `Closes #N` vào đó — nguồn chân lý có
sẵn, chỉ là chưa ai đọc.

Ba quyết định phải giữ:

- **Chỉ `Closes`/`Fixes`/`Resolves`, KHÔNG `Refs`.** `with_issue_ref()` chấp nhận
  `Refs #N` có chủ ý, cho PR làm một phần việc. Làm một phần nghĩa là issue còn việc, nên
  nó ở lại hàng đợi. Rút nó ra theo `Refs` là **chôn việc đang sống**.
- **Chỉ `--state open`.** PR đóng-không-merge biến mất khỏi map và issue tự quay lại hàng
  đợi. Mở rộng sang `--state all` sẽ chôn issue đó vĩnh viễn và im lặng — tệ hơn hẳn cái
  việc-trùng mà bản vá này ngăn.
- **`gh_json_required`, không phải `gh_json`.** Nuốt lỗi thành map rỗng là dựng lại đúng
  cái bug đang sửa, không một dòng báo.

**NGOẠI LỆ `changes-requested` — thiếu nó thì bản vá tự đào một hố sâu hơn cái nó lấp.**
Một vòng rework **LUÔN** có PR mở: `tal pr` chèn `Closes #N`, và rework push lại cùng
nhánh nên PR không đóng. Không trừ ra thì issue vừa bị review trả về bị bỏ qua với đúng
câu *"bản sửa đã có, đừng làm lại"* — ngay lúc review vừa phán bản sửa **CHƯA** đạt. Tệ
hơn, nó **TỰ DUY TRÌ**: không ai nhặt rework ⇒ PR mở mãi ⇒ issue chôn mãi. Cùng họ với
bug lịch sử ghi ở docstring `gate_open()`. Và `changes-requested` là ưu tiên **CAO NHẤT**
của hàng đợi, nên biến nó thành mục bị bỏ qua là **đảo ngược chính xác** thứ tự mà hàng
đợi tồn tại để giữ.

Ngoại lệ này gỡ **đúng một** lý do bỏ qua và không gỡ gì khác — lease sống vẫn thắng, nên
hai session không bao giờ được mời vào cùng một vòng rework.

**Phạm vi phủ.** Truy vấn đọc `--limit 100` PR mở đầu tiên. Quá đó nó hỏng **theo chiều
MỞ** — một issue không nhận diện được thì ở LẠI hàng đợi, tức xấu nhất là làm trùng, không
bao giờ là chôn việc. Chạm trần thì phân trang, **đừng chỉ nâng số**.

**Nhãn để nguyên.** Đối chiếu với trạng thái đo được ở mỗi lần chạy tốt hơn một lần ghi
nhãn mà không ai xem lại — đó là hình dạng lỗi kho này gặp đi gặp lại.

---

## 8. Verdict rơi SAU merge bị từ chối — ba cổng

**Hành vi.** `review-claim` và `merge-batch` không loại trừ nhau, và cuộc đua là có thật:
một lease review giành lúc 14:17:49Z, `merge-batch` merge PR lúc 14:18:38Z, và verdict
`changes` — đúng, `(blocking)` — rơi lúc 14:20:11Z, **muộn 93 giây**. Nó không gác được
gì: nó dán `agent:changes-requested` + `status:blocked` lên một issue có PR đã merge và
đóng, trong khi phát hiện blocking thật nằm trên nhánh base, không ai sở hữu.

Ba cổng đóng cửa sổ đó, từ rẻ tới cuối cùng:

1. **`review-claim` từ chối PR không ở trạng thái OPEN** — không có gì để review, không
   phí một vòng. **Ngoại lệ:** `CLOSED` **không** merge KHÔNG gộp chung với `MERGED` —
   nếu issue chưa `shipped`/chưa đóng, `tal` trả nó về `agent:ready` thay vì để mắc kẹt ở
   `awaiting-review` vĩnh viễn.
2. **`merge_blockers` loại khỏi lô mọi PR đang có lease review SỐNG** — verdict được rơi
   trước. Lease quá TTL thì KHÔNG chặn (session review đã chết; một lease mồ côi giữ con
   tin mọi lượt merge là rào tệ hơn không rào).
3. **`review-verdict` đọc lại trạng thái PR ngay trước khi ghi.** `MERGED` ⇒ từ chối, nhả
   lease review, và bảo mở **issue MỚI** nếu phát hiện blocking vẫn đứng — nó đang nằm
   trên nhánh base rồi. `CLOSED` không merge đi cùng đường reset như (1). **Không đọc được
   trạng thái thì cũng từ chối** (không đo được ≠ OPEN), nhưng **giữ lease** để thử lại.

**Cổng (2) phải nằm trong `merge_blockers`, không nằm riêng trong `merge-batch`.** Ngày
14–15/08 ba session độc lập cùng merge đè lên một review đang chạy, và cả ba đi đường
`gh pr merge` — không qua `tal`. Verdict rơi sau khi PR đã khép nên không ghi lên được;
một trong ba mang verdict CHANGES với ba điểm blocking nằm nguyên trên nhánh base mấy
tiếng. Ba session trong một ngày không phải ba lần cẩu thả — đó là thiếu rào, và lý do có
tính hệ thống: mọi session đẩy PR bằng **cùng một tài khoản GitHub** nên không ai duyệt
được PR của chính tài khoản mình, ai thẩm tra xong cũng rơi về `gh pr merge`.
`merge_blockers` là điểm hội tụ của **cả bốn** đường merge trong `tal`, nên đặt ở đây
khoá được cả bốn bằng một chỗ. (Đường `gh pr merge` được `hook-guard` phủ riêng — xem
`references/enforcement-map.md`.)

**Trên đường từ chối, sổ thường giữ nguyên như merge để lại.** Đường reset cho PR bị bỏ
là ngoại lệ có chủ ý: nó **có** ghi `queued` + `agent:ready`, nhưng **không bao giờ** khi
issue đã mang nhãn shipped, sổ `shipped`, hoặc GitHub báo `state: closed`.

---

## 9. Merge đòi verdict TRÊN GITHUB, khớp HEAD

**Hành vi.** Nhãn sống sót qua một lần push mới, và ledger thì sửa được — không cái nào
là bằng chứng rằng **bản này** đã được review. Nên `merge_blockers` đòi mảnh bằng chứng
thứ tư, trên cả ba thứ kia (`reviewPassed`, trộn sạch, CI): một comment
`tal:review verdict=pass` **trên GitHub** có tiền tố `sha=` khớp HEAD của PR
(`pr_verdict_pass_evidence`). Không có ⇒ từ chối; `--force` đòi `--note` và đăng lời bỏ
qua lên chính PR.

Hai chi tiết, mỗi cái mất một vòng mới đúng:

- **Bằng chứng lấy MỘT lần, tại cổng** (`merge_blockers` trả nó về) và dùng lại khi ghi
  sổ. Bất kỳ commit nào rơi lên nhánh PR giữa cổng và sổ sẽ đổi HEAD, và một lần tra thứ
  hai khi đó ghi `verdict=KHÔNG_CÓ` cho một merge đã qua cổng. SHA được ghi là bản
  reviewer **thật sự đã đọc**.
- **Mở khoá một lease REVIEW (`tal unlock pr-<N>`) luôn đòi `--note`** — không chỉ khi
  kèm `--force` — và lời mở khoá được đăng lên PR. Một lease review đặt tên session còn
  nợ verdict; vứt nó đi trong im lặng là mở lại đúng cuộc đua ở §8.

**Verdict MỚI NHẤT trên một sha là câu trả lời.** `pass` rồi `changes` trên **cùng** sha
⇒ hết bằng chứng. Bản cũ chỉ tìm `pass` nên một `changes` mới hơn bị lờ.

---

## 10. Merge từ chối PR có base là nhánh phát hành — và `--force` KHÔNG mở nó

**Hành vi.** Mọi cổng ở trên hỏi *"PR này đủ tốt chưa?"*. Cổng này hỏi câu khác và hỏi
**trước tất cả**: *"nó rơi xuống ĐÂU?"*. `promotion_base_verdict(base, promote, …)` trả
`"promotion"` khi base là nhánh phát hành mà không khai `--promote`, và `"foreign"` khi
base chẳng phải nhánh nào trong hai nhánh đã khai.

**Vì sao.** Khi một PR *base → promotion* merge, GitHub **âm thầm đổi base của MỌI PR
đang mở nhắm nhánh base sang nhánh phát hành** (`automatic_base_change_succeeded` trong
timeline), giữ nguyên tiêu đề, thân và nhãn. Ngày 12/08 bốn lượt phát hành kéo **chín** PR
qua, và một trong số đó được merge vào nhánh phát hành lúc 11:32 — giữa giờ nghỉ trưa.
Người gọi đọc `mergeStateStatus: CLEAN` rồi merge; không ai đọc lại `baseRefName`, vì nó
đúng lúc PR được mở.

**Cái giá đã DỜI CHỖ, và rào vì thế đáng giá hơn chứ không kém đi.** *VÍ DỤ (kho tiêu
thụ):* dưới mô hình release train, merge vào nhánh phát hành **không kích hoạt gì**; CD
được nạp bằng cách push một tag. Nhưng nhánh phát hành là nơi tag được cắt ra, và một tag
chạy triển khai production không người trông. Code bị kéo nhầm lên đó là code **chưa qua
cổng nào**, nằm đúng chỗ lượt phát hành kế tiếp sẽ lấy. Bán kính nổ dời từ "lần merge"
sang "lần phát hành kế tiếp" — nơi không ai đang tìm nó.

Ba cạnh có chủ ý:

- **`--force` KHÔNG mở nó.** `--force` là thứ mọi session gõ hằng ngày để bỏ cổng review;
  cho nó vượt luôn cổng này là giết cổng ngay ngày đầu. `--promote` là một câu **khẳng
  định về ý định**, không phải một cách nói "kệ đi".
- **`--promote` không mở một base LẠ.** Một PR nhắm `release/x` vẫn bị từ chối — người gọi
  đó đang nhầm, không đang phát hành.
- **Không đọc được base ⇒ cho qua.** Rào này canh đúng một tai nạn, không canh mạng chập
  chờn. Fail-closed ở đây sẽ giết mọi lượt merge mỗi khi GitHub chậm, và rào sẽ bị gỡ
  nguyên khối.

Trên đường `--promote` còn một cổng nữa: `promotion_only_files()` từ chối lượt phát hành
khi **không chứng minh được** rằng nó không xoá mất file chỉ tồn tại trên nhánh phát hành
(hotfix vá thẳng production). `--no-renames` là cố ý — câu hỏi là về **sự tồn tại của
đường dẫn**, không phải phỏng đoán tương đồng của git. Fetch mới cả hai ref ngay trước khi
đo; ref cũ biến rào an toàn thành một lời nhắc.

---

## 11. CI ĐỎ là rào cứng, và "chưa biết" KHÔNG phải "đã xanh"

**Đọc tiêu đề này theo nghĩa đen.** Phần dưới phủ đúng **một đường**: đường đi qua `tal`.
Đường thứ hai — `gh pr merge` gõ tay và nút xanh trên web — được `hook-guard` phủ riêng
(§11c), và **chỉ khi lệnh đi qua hook**. Đừng trích mục này thành "CI đã được gác".

**Vì sao không có rào cơ học ở GitHub.** *VÍ DỤ (kho tiêu thụ):* repo private trên gói
hiện tại **không bật được** required status checks —
`gh api repos/<owner>/<repo>/branches/<base>/protection` trả
`403: Upgrade to GitHub Pro or make this repository public`. Đó là **giới hạn của gói**,
không phải cấu hình sai. Ở một kho tiêu thụ bật được branch protection thì phần lớn mục
này thành thừa — và đó là kết cục mong muốn.

### 11a. `state == "fail"` chặn merge

**Hành vi.** `merge_blockers` thêm một blocker mở đầu bằng hằng số `CI_RED`; `cmd_merge`
dò **đúng tiền tố ấy** để tách nó ra và biến nó thành rào `--force` không mở được. Rào áp
cả trên đường `merge-batch` — PR đỏ bị loại khỏi lô. Lời từ chối gọi **tên check đã đỏ**
(`red_check_names`), không đổ cả bảng.

**Vì sao.** CI chạy trên commit **trộn** (base + nhánh), nên một PR đỏ vào base kéo mọi
PR sau đó đỏ theo, và tác giả của chúng đi săn ma. Đã đo: một PR merge lúc 15:05:50Z với
một check **đã đỏ trên chính PR đó**; từ commit ấy trở đi mọi PR vào base đều đỏ. Một PR
không chạm dòng code nào liên quan cũng đỏ, và tác giả mất ba vòng để chứng minh chỗ hỏng
không phải của mình. Cửa sổ đo được: 45 phút.

Việc in **tên** check thay vì cả bảng chính là để không lặp lại ba vòng đó.

**Lối ra duy nhất là `tal merge <pr> --ci-red --note "<vì sao>"`,** và note được đăng lên
PR. `--ci-red` là một khẳng định về ý định; `--force` thì không.

### 11b. `state == "pending"`, và bucket LẠ rơi về phía CHƯA XONG

**Hành vi.** `CI_DONE_BUCKETS = {"pass", "fail", "cancel", "skipping"}`. `pr_checks()`
trả `"pending"` khi `buckets - CI_DONE_BUCKETS` khác rỗng — **kể cả một bucket chưa từng
thấy**. `merge_blockers` biến nó thành blocker mở đầu bằng `CI_PENDING`, và `cmd_merge`
dò tiền tố đó y như `CI_RED`.

**Vì sao.** Rào ở §11a chỉ bắt ca CI nói **ĐỎ**. Ca CI **CHƯA NÓI** đo được hai lần trong
một phiên, cả hai đều merge lúc check còn chạy — một trong hai có check xanh **39 giây
SAU** lần merge. Không cái nào đỏ, nên rào §11a im lặng đúng thiết kế. Cái giá thì y hệt:
CI chạy trên commit trộn.

**`skipping` là một KẾT LUẬN, không phải một lần chờ.** Một job có `paths`/`if` không bao
giờ khớp sẽ ở `SKIPPED` mãi mãi. Đếm nó là chưa-xong sẽ chặn gần như mọi thứ, và **một
rào chặn mọi thứ thì bị xoá**. `wait_checks()` đã học đúng bài đó sớm hơn.

**Chiều mặc định là CỐ Ý.** Danh sách khai cái gì **đã xong**, nên một thay đổi từ vựng
của `gh` hay một trạng thái mới của GitHub **fail-closed**. Chặn nhầm thì thấy ngay bằng
một lệnh; cho qua nhầm thì vô hình cho tới lúc nhánh base đỏ.

**Nó TỪ CHỐI, không CHỜ.** Gõ lại một lệnh rẻ hơn một vòng ngủ bên trong `tal` (timeout,
Ctrl-C giữa chừng, cổng lô bị giữ mở trong lúc nó ngủ). Muốn đứng chờ thì `tal pr-merge`
đã có sẵn vòng đó (`wait_checks`, `--timeout`) — không có lý do dựng cái thứ hai.

**Một lối ra cho cả hai sắc thái, cố ý:** `--ci-red --note`. Hai cờ cho hai sắc thái của
cùng một khẳng định chỉ tạo thêm một thứ nữa để quên nối vào `merge-batch`. Comment đăng
lên PR ghi *MERGE KHI CI CHƯA XONG* thay vì *CI ĐỎ*, nên sổ vẫn phân biệt hai ca.

**Quan hệ với `--require-ci` (#1454).** Cờ đó trả lời câu **khác**: "có bắt PR phải CÓ CI
xanh không" — mặc định **KHÔNG**, vì ở nhiều kho tiêu thụ CI của một PR vào base là full
suite. Rào §11a/§11b trả lời: check **đang chạy**, tức nó **sẽ** nói; merge lúc này không
tiết kiệm được gì, nó chỉ dời câu trả lời sang một commit trộn nơi người trả giá là tác
giả của các PR sau. `merge_blockers` giữ hai ca đỏ/pending **ngoài** phạm vi `require_ci`
— cờ đó tắt không được tha chúng.

> **Phạm vi thay đổi theo hình dạng CI của kho tiêu thụ.** *VÍ DỤ (kho tiêu thụ):* nếu
> repo dựng CI sao cho PR vào nhánh base kích **0 workflow** (CI chỉ chạy ở PR phát
> hành), thì `pr_checks()` trả `("none", [])` cho mọi PR mà `tal` gom, và **cả hai rào im
> lặng đúng thiết kế** — chúng chỉ còn cắn trên PR phát hành. Khi đó "PR này merge được"
> phải đọc là *không có đối chứng nào phản đối*, KHÔNG phải *CI đã xanh*; đối chứng cho
> một PR là **test hẹp chạy tại máy** (`tal tests --run`), còn đối chứng cho cả lô là PR
> phát hành. Đó không phải rào hỏng — nhưng bật `--require-ci` trong thế giới đó là chặn
> **MỌI** PR vào base, vĩnh viễn.

### 11c. `hook-guard` phủ nốt đường `gh pr merge`

**Hành vi.** Khi lệnh Bash chứa `gh pr merge <N>`, hook đọc `pr_checks(N)` và **deny** nếu
đỏ hoặc chưa xong, kèm tên check và câu "dùng `tal merge <N>` để đi qua cổng đầy đủ".
Phép kiểm này xét **nội dung lệnh**, không xét chỗ đứng, nên nó chạy cả khi lệnh gõ từ
gốc repo.

**Vì sao.** `gh pr merge` là đường **duy nhất** không có rào ở phía `tal`, và nó chính là
đường ba session rơi vào ở §8. Đặt phép kiểm ngoài phần "chỉ chạy trong worktree" là bản
sửa của lỗi *"rào đúng mà không bao giờ chạy tới"* — lần thứ năm cùng hình dạng.

**Gỡ thì hỏng gì.** Đưa nó trở vào nhánh chỉ-trong-worktree ⇒ `git push origin <base>` từ
gốc repo exit 0, không chặn. Đo bằng payload thật trước khi tin bất kỳ rào nào trong hook.

---

## 12. Chín hợp đồng hành vi của lượt hardening tổng lực (#2300)

Một lượt audit đối kháng toàn bộ `tal` (54 phát hiện từ 4 auditor độc lập) sửa trong MỘT
PR. Những hợp đồng **ĐỔI** mà người sửa công cụ phải biết:

1. **Sổ THẮNG — nhãn là cache một chiều.** Gỡ nhãn dead-letter bằng `gh label` sẽ bị đồng
   bộ dán lại. Đường chính danh mở khoá là **`tal requeue <N> --note "<vì sao lần này sẽ
   khác>"`**: reset `review_rounds`/`reaps` (chuỗi thất bại làm lại), **GIỮ** `attempts`
   + history (sử liệu), gắn lại nhãn ready. `tal unlock` **KHÔNG** reset counter — nó là
   lệnh gỡ khoá, không phải ân xá — và **cảnh báo** khi counter sắp tái dead-letter, để
   người khỏi ngạc nhiên ở lần claim kế tiếp. `requeue` từ chối issue đang có lease sống,
   và bắt buộc `--note`.
2. **Verdict phải là của người GIỮ lease review, trên ĐÚNG bản đã đọc.** `review-claim`
   ghim `headRefOid` vào payload của ref; `review-verdict` đòi chính session giữ ref đó và
   so sha ghim với head sống. Coder push bản mới giữa chừng ⇒ verdict `Fail` kèm nhả
   lease, phải claim lại và đọc diff mới. Một verdict `pass` reset `review_rounds` về 0:
   nó đếm **chuỗi thất bại liên tiếp**, không phải tổng đời issue.
3. **"Đã code" = đã BÀN GIAO PR (`tal pr`), không phải đã từng claim.** Claim-để-đọc rồi
   release no-op không còn làm mất quyền review. Attribution ghi ở trường `coders` của
   ledger (không bị cắt như history), và `assert_not_own_work` đọc từ đó — áp cho **cả ba
   cửa**: `review-claim`, `review-verdict`, `merge`. Chặn một cửa thì hai cửa kia vẫn mở,
   và đã đi qua cả hai. Trên đường lô, nó áp cho **TỪNG PR** trong `merge-batch`: PR của
   chính session đang chạy bị loại khỏi lô kèm comment.
4. **`tal merge` merge TRƯỚC, dọn SAU.** Thứ tự cũ (`remove_worktree` rồi
   `gh pr merge --delete-branch`) đã cắn thật: merge fail vì cờ `mergeable` bất đồng bộ,
   nhưng worktree + branch cục bộ + thẻ lease đã bị xoá — không gì rollback được. Lý do
   lịch sử của thứ tự cũ là `--delete-branch` không xoá được branch cục bộ đang bị
   worktree giữ; giải bằng cách **không dùng** `--delete-branch` và xoá nhánh remote qua
   API sau khi merge OK. Ngoài ra, một merge lẻ bị **CHẶN** khi cổng `merge-batch` đang
   chạy: suite của lô phải kết luận trên một base không đổi.
5. **Claim GIỮ nhãn review đang gắn** (`preserve` trong `set_state_labels`). Chỗ duy nhất
   tháo chúng là `tal pr` khi push bản mới.
6. **Kỷ luật lỗi API — "không đo được" RAISE thay vì trả rỗng** ở mọi phép đo dẫn tới một
   quyết định phá huỷ (ledger, refs, nhãn, `pr_issue`, `wait_checks`…). Chỉ 404 **THẬT**
   mới được coi là "không còn" (`Gone`). `--paginate` nhiều trang được ghép đúng
   (`_json_pages`) — một issue >100 comment không còn bị đọc thành "sổ trắng". `gh_json`
   vẫn nuốt lỗi **có chủ ý** cho những câu hỏi lành tính ("PR này tồn tại chưa?" — 404 là
   câu trả lời hợp lệ); mở rộng hợp đồng cho cả 33 người gọi nó là một thay đổi riêng,
   phải đọc từng chỗ.
7. **`set_state_labels` BỎ lần ghi khi không đọc được nhãn hiện tại.** `default=[]` làm
   PUT trên một danh sách rỗng giả — một cú API chớp là mất sạch nhãn không-managed của
   issue.
8. **`--force-region` tách khỏi `--force`.** Vượt rào vùng file đang bị lease khác giữ là
   một quyết định riêng, phải nói to. `--force` chỉ nói "nhặt issue chưa-ready/dead-letter
   hộ người".
9. **Rào vùng chạy TRƯỚC khi tạo ref**, và quyền "nhận lại" đo **theo TỪNG KEY** chứ không
   theo root: sổ của root chỉ chứng minh được các key mà chính lease root liệt kê. Trước
   đây một ref `issue-<con>` do session khác `--split` giữ bị "adopt" nhầm, và lần release
   sau xoá luôn lease sống của họ.

---

## 13. Worktree mồ côi — DỜI trước, XOÁ sau

**Hành vi.** Trạng thái nguy hiểm nhất của một worktree không phải "chưa dọn" mà là **nửa
chết**: đăng ký git đã bị prune nhưng thư mục còn nguyên. `cd` vào đó vẫn thành công, và
mọi lệnh git từ trong đó **im lặng giải về repo cha** — không một cảnh báo. Một phiên
dính bốn lần, một lần đã commit nhầm lên nhánh của session khác.

Ba rào:

1. **`remove_worktree` không bao giờ để lại nửa-chết.** Xoá thất bại ⇒ **RENAME** thư mục
   sang `<tên>.orphan-<timestamp>` TRƯỚC (git hết trỏ vào đường dẫn cũ, prune từ đây là an
   toàn), rồi mới `rmtree` bản đã dời — xoá sót cũng vô hại vì tên nó tự khai là rác.
   Rename cũng thất bại ⇒ **không prune, không xoá branch**, trả `False`. Worktree chưa
   dọn là trạng thái an toàn hơn worktree nửa-chết.
   *`rmtree` thẳng vào chỗ cũ mà chết dở dang (permission, hardlink của thư mục phụ thuộc)
   thì có thể mất `.git` trong khi phần còn lại của cây vẫn đứng — đúng định nghĩa mồ côi.*
2. **`assert_worktree_attached(path)`** — so `git rev-parse --show-toplevel` với chính thư
   mục đang đứng; lệch ⇒ `Fail` (exit 4) với thông điệp "WORKTREE MỒ CÔI". Gắn ở
   `ensure_worktree_branch` (chặn tái dùng lúc claim) và ở `do_assert` (cổng của mọi thao
   tác ghi). Trong `do_assert` nó nằm **SAU** các phép kiểm lease, để thông điệp lease
   (released / hết hạn / fenced) — vốn đúng và đủ để dừng tay — không bị che.
3. **Vỏ orphan phải HỘI TỤ.** `remove_orphan_tree()` gỡ ACL `deny delete` (một trình quản
   lý gói trên macOS có thể đặt nó lên thư mục vendor), bắt lỗi, rồi **đọc ngược lại đường
   dẫn** — chỉ khi nó thật sự biến mất mới trả `True`. `shutil.rmtree(ignore_errors=True)`
   từng vừa bỏ sót một vỏ thư mục, vừa khai thành công. `cleanup_orphan_worktrees()` quét
   lại mọi `*.orphan-*` còn sót từ những lượt trước ở lần chạy sau.

**Gỡ thì hỏng gì.** Đảo thứ tự (xoá trước, dời sau) ⇒ mất `.git` giữa chừng và sinh ra
đúng cái mồ côi mà rào này chống. Bỏ `assert_worktree_attached` ⇒ một worktree mồ côi
được trao cho session như đồ thật, và nếu repo cha tình cờ đứng đúng branch thì không có
gì báo. Cho `remove_orphan_tree` trả `True` khi chưa xoá xong ⇒ `gc` không bao giờ hội tụ.

---

## Khi bạn thêm hoặc sửa một rào

Câu hỏi đầu tiên **không phải** "diễn đạt thế nào". Nó là **"cái này được cưỡng chế ở
đâu"** — xem `references/enforcement-map.md`, phần thủ tục cuối file. Ba phép thử rút ra
từ chính những mục ở trên, và cả ba đều là lỗi đã trả giá:

1. **Test phải lái LỆNH, không khớp chuỗi trong mã nguồn.** `if False and …` để nguyên
   chuỗi và để nguyên màu xanh (§4).
2. **Rào phải chạy tới được.** Đo bằng payload thật, không đọc comment (§11c).
3. **Không đo được ≠ đo ra sạch.** Mọi đường lỗi phải lệch về phía an toàn, và phía an
   toàn thì tuỳ chỗ: giữ worktree (§6), không đóng issue (§2), không stamp nhãn (§6d),
   nhưng **cho qua** khi không đọc được base (§10) — vì fail-closed ở đó sẽ giết mọi lượt
   merge và rào sẽ bị gỡ nguyên khối.
