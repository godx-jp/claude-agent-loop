# Runbook — sự cố đã xảy ra thật, và lối ra

Tra theo **TRIỆU CHỨNG**. Người mở file này đang bị kẹt, nên mỗi mục có đúng ba phần:
**triệu chứng → chẩn đoán → lối thoát**.

File này không phải luật. Luật ở [`discipline.md`](discipline.md) — mở nó khi bạn đang
nghi ngờ, mở file này khi có thứ đang hỏng.

## Bảng tra

| Bạn đang thấy | Mục |
|---|---|
| Mọi lệnh Bash đều bị deny, kể cả `pwd` và `cd` | §1 |
| Bị deny khi chạy test ("full suite BỊ CẤM") | §2 |
| `tal assert` báo HẾT LEASE / MẤT LEASE / FENCED | §3 |
| `không thấy .tal-lease.json` mà `tal status` vẫn ghi tên bạn | §4 |
| Một issue khoẻ mạnh mang nhãn dead-letter | §5 |
| PR đóng mà không merge, nhánh thì đã bị xoá | §6 |
| Cổng merge báo "full suite ĐỎ" trong khi môi trường lành | §7 |
| `tal queue` nói hàng đợi rỗng — có tin được không | §8 |
| `tal review-queue` rỗng, nhưng rõ ràng có PR chờ | §9 |
| `git push` bị từ chối non-fast-forward | §10 |
| Không biết mã thoát vừa rồi nghĩa là gì | §11 |

---

## §1. Session bị nhốt: mọi lệnh Bash đều bị deny

**Triệu chứng.** `pwd`, `cd ..`, và cả cái `tal claim` mà chính thông điệp deny mách đều bị
chặn, kèm dòng đại ý *"worktree này (issue #N) đã NHẢ LEASE"* hoặc *"worktree này thuộc
session khác"*.

**Chẩn đoán.** Shell đang đứng bên trong một worktree mà lease đã nhả (hoặc thuộc session
khác), và rào lease đang phán theo **CWD** thay vì theo nội dung lệnh. Đứng ở đâu không phải
bằng chứng bạn đang ghi cái gì — nên rào chặn cả những lệnh không ghi gì, kể cả lệnh dùng để
tự gỡ.

**Lối thoát.** Bản `tal` hiện tại đã sửa: hai rào lease chỉ áp cho lệnh **thực sự có đích
ghi** nằm trong worktree có lease (`hook-guard` quy lệnh Bash về đường dẫn đích rồi mới hỏi
lease). Nếu vẫn gặp:

1. `cd` ra khỏi worktree đó — về gốc repo.
2. `tal status` xem lease thật đang thuộc về ai.
3. `cd` vào đúng worktree mà lô của bạn đang giữ, rồi `tal assert`.

> **Mục này từng nói một chuyện khác, và chuyện đó nay không thể xảy ra nữa.** Nó từng là:
> *"bản `tal` ở worktree chính đã cũ — hook chạy bản của cây chính, không phải bản của
> nhánh"*, kèm một lệnh checkout để chữa. Cả lớp hỏng đó đến từ việc `tal` là **file được
> track**, nên mỗi nhánh mang một bản công cụ tự phán xử chính mình. `tal` giờ là plugin:
> một bản trên mỗi máy, gắn phiên bản theo lượt cài plugin, không nhánh nào che được nó.
>
> Hình dạng ấy đáng nhớ: **bản sửa tồn tại, đã merge, và vẫn không có tác dụng** là lớp
> hỏng tệ nhất của một công cụ tự động. Xem [discipline §8](discipline.md).

## §2. Bị deny đúng lúc chạy test

**Triệu chứng.** `hook-guard` deny với *"Full suite BỊ CẤM trong worktree của vòng lặp"* —
trong khi bạn tin mình đang chạy một lệnh HẸP.

**Chẩn đoán.** Rào so khớp **substring** với các lệnh khai ở `fullSuite`. Lệnh bạn gõ mang
nguyên một chuỗi con của một lệnh full-suite (thường là một cờ chỉ cần cho lượt chạy toàn
bộ, bị dán thêm vào lệnh hẹp cho "chắc").

**Lối thoát.**

1. **Đừng tự chọn lệnh** — `tal tests` in ra đúng những lệnh mà diff này kéo theo,
   `tal tests --run` chạy chúng. Bảng suy ra chúng là `affectedTests` trong
   `.claude/agent-loop.json`.
2. Nếu lệnh của bạn **đúng ra phải chạy được**, thì thứ cần sửa là config, không phải lệnh:
   thêm nó vào `affectedTests`. `tal` tự trừ `affectedTests` khỏi danh sách cấm, nên một
   lệnh nằm ở cả hai chỗ vẫn chạy được.
3. Đừng gõ tay một lệnh rộng hơn để đi vòng. Lần sau sẽ không ai gõ.

## §3. `tal assert` báo mất lease giữa chừng

**Triệu chứng.** `HẾT LEASE` / `MẤT LEASE` / `FENCED` / `LEASE QUÁ HẠN` (mã thoát **4**).

**Chẩn đoán.** Ref CAS không còn, hoặc sổ ghi chủ là session khác, hoặc epoch của bạn đã
bị vượt. Lease đã được cấp cho người khác.

**Lối thoát. DỪNG.** Không push, không mở PR. Commit của bạn lúc này là rác — đừng biến một
xung đột thành hỏng dữ liệu.

Nếu `tal status` báo `MISMATCH: ref tồn tại nhưng sổ không ghi chủ nào` **và** bạn chắc chắn
không có session nào khác đang chạy (`tal status` không liệt kê lease nào):

```sh
tal unlock issue-<N> --force --note "vì sao bạn chắc chắn"
tal claim <N>
```

`--force` là **can thiệp tay**. Bình thường hãy để `tal gc` thu hồi theo TTL; cướp lease của
một session còn sống chính là thảm hoạ mà cả hệ thống này sinh ra để ngăn.

Với lease **review** (`tal unlock pr-<N>`), `--note` là **bắt buộc** ngoài `--force`: unlock
được comment lên PR, và một lease review đang nêu tên session còn nợ kết luận — vứt nó trong
im lặng là mở lại đúng cuộc đua "kết luận sau khi đã merge".

## §4. Mất THẺ không phải mất LEASE

**Triệu chứng.** `renew` / `assert` / `pr` / `release` cùng thoát **3** với *"không thấy
`.tal-lease.json`"*, trong khi `tal status` vẫn liệt kê issue là do session của bạn giữ và
TTL chưa hết.

**Chẩn đoán.** Thẻ trên đĩa chỉ là **cache** của một trạng thái sống trên GitHub. Một
`git worktree prune`, một lần dời thư mục, hay một lượt `gc` dở dang đều lấy mất nó trong
khi ref và sổ còn nguyên.

**Lối thoát.** Đừng với tay vào hai lệnh nghĩ ra đầu tiên — `claim` **bump epoch** (đúng cái
fencing token sinh ra để ngăn), `unlock --force` **vứt một lease đang sống**:

```sh
tal adopt              # tự suy issue; hoặc: tal adopt <N>
tal assert             # xanh lại, CÙNG epoch
```

`adopt` dựng lại thẻ **từ sổ** và không làm gì khác — nó cố ý không ghi lên sổ, vì một dòng
history vô hại cũng sẽ lặng lẽ gia hạn lease. Nó **từ chối** (mã **5**) nếu sổ ghi tên một
session khác, và từ chối nếu ref CAS đã biến mất — trường hợp thứ hai nghĩa là lease thật sự
đã bị thu hồi, và `tal claim <N>` (epoch + 1) mới là câu trả lời đúng.

## §5. Một issue khoẻ mạnh mang nhãn dead-letter

**Triệu chứng.** Issue trông bình thường nhưng `tal queue` bỏ qua nó với lý do
`dead-letter, chờ người`; `tal claim` từ chối.

**Chẩn đoán.** Ngưỡng dead-letter đếm **số vòng review thất bại**, không đếm số lần claim.
Một issue mang nhãn từ bản `tal` cũ (đếm theo claim) sẽ kẹt vô lý.

**Lối thoát.** **Đừng gỡ nhãn bằng tay** — trạng thái được đồng bộ lại từ sổ, nên nhãn gỡ
tay quay về, và `unlock` thì giữ nguyên bộ đếm nên lần claim sau lại dead-letter tiếp. Đường
hợp lệ là:

```sh
tal requeue <N> --note "vì sao lần này sẽ khác"
```

Nó đặt lại bộ đếm vòng review / số lần bị thu hồi và mở lại cổng cho issue. `--note` bắt
buộc: đây là một quyết định của người, và nó được ghi lại.

## §6. PR bị đóng mà không merge, nhánh thì đã bị xoá

**Triệu chứng.** `gh pr merge --delete-branch` báo `Head branch is out of date`, merge
**thất bại**, nhưng nhánh **vẫn bị xoá** ⇒ PR đóng theo.

**Chẩn đoán.** `--delete-branch` chạy độc lập với kết quả merge.

**Lối thoát.** Commit vẫn còn trong worktree cục bộ. Merge base vào nhánh, push lại, mở PR
mới.

**Cách để không gặp lại.** Bật `delete_branch_on_merge` ở cấp repo, rồi bỏ hẳn
`--delete-branch` — cái bẫy này biến mất. Và đi qua `tal merge` thay vì `gh pr merge`: nó
merge **trần** trước, xoá nhánh remote sau, đúng thứ tự ấy vì lý do này.

## §7. Cổng merge báo "full suite ĐỎ" trong khi môi trường lành

**Triệu chứng.** Cổng đỏ với một lỗi kiểu "không tìm thấy class", "không mở được file",
"command not found" — nhưng chạy lại bằng tay thì môi trường hoàn toàn lành.

**Chẩn đoán.** Đọc **mã thoát**, không đọc chữ "ĐỎ":

- **3 = CỔNG HỎNG** (môi trường / cây tạm) — **không** phải test đỏ, không assertion nào
  chạy.
- **2 = test đỏ thật.**
- **75 = session khác đang giữ** cổng (hoặc lease).

`tal` phân biệt theo **triệu chứng** chứ không theo vị trí gọi, nên mã 3 là kết luận của
công cụ, không phải phỏng đoán của bạn.

**Lối thoát.** Với mã 3: sửa môi trường rồi chạy lại — đừng đi tìm một test hỏng không tồn
tại. Nguyên nhân hay gặp là `setup` chưa theo kịp một lệnh mới thêm vào `fullSuite`. Muốn
thử chính cái cổng mà không merge gì: `tal merge-batch --gate-only`.

## §8. Hàng đợi rỗng là một PHÉP ĐO, không phải giá trị mặc định

**Triệu chứng.** `tal queue` / `tal review-queue` / `tal merge-queue` in `hàng đợi rỗng` —
trong khi bạn biết có issue đang mở.

**Chẩn đoán.** Đây là lớp bug nguy hiểm nhất của cả nhóm lệnh này, và nó đã cắn thật: hàm
đọc JSON từ `gh` trả về **giá trị mặc định** cho **mọi** mã thoát khác 0 — hết quota, mạng
hỏng, token hết hạn, thiếu `gh` — chứ không riêng 404. Ba truy vấn tìm việc dùng
`default=[]`, nên "gọi hỏng" và "backlog rỗng thật" là **cùng một giá trị**, in ra cùng một
câu trấn an, cùng thoát 0.

Lời nói dối ấy chỉ về **sai hướng**: skill dạy rằng hàng đợi rỗng thì báo cáo và kết thúc
lượt — nên một session tuân thủ đúng luật sẽ báo "hết việc" trong khi backlog đầy, và một
vòng chạy nền sẽ lặng lẽ ngủ qua từng cửa sổ rate-limit.

Đã đo: với quota GraphQL cạn, lệnh in `hàng đợi rỗng` và thoát 0 trong khi ba issue đang mở
với nhãn ready (đo lại qua REST, còn quota).

**Lối thoát.** Ba lệnh tìm việc nay dùng đường đọc **bắt buộc**: chúng **thoát khác 0** với
`KHÔNG ĐO ĐƯỢC` thay vì báo rỗng. Đọc mã thoát ấy là **"hỏi lại sau"**, không bao giờ là
"hết việc".

```sh
gh api rate_limit --jq .resources     # xem còn bao nhiêu, và bao giờ reset
```

REST và GraphQL có ngân sách **riêng**, nên `gh api repos/...` thường vẫn chạy khi
`gh pr list` đã tắc.

> Chỉ ba chỗ gọi đó đổi. Những chỗ gọi còn lại cố ý giữ nguyên hành vi nuốt lỗi — nhiều chỗ
> **dựa** vào nó (hỏi "PR này đã tồn tại chưa?" thì 404 là câu trả lời hợp lệ). Nới hợp đồng
> cho tất cả là một thay đổi khác, phải đọc lại từng chỗ gọi.

## §9. Hàng đợi review rỗng phải nói AI đang giữ

**Triệu chứng.** `tal review-queue` trả `eligible: []` trong khi rõ ràng có PR đang chờ
review.

**Chẩn đoán.** `eligible: []` từng mang **hai** nghĩa hoàn toàn khác nhau — "không PR nào
chờ review" và "có PR chờ, nhưng session khác đang giữ lease của chúng". Luật "hàng đợi rỗng
→ báo cáo, kết thúc lượt" khiến một session tuân thủ đúng luật báo *hết việc* trong khi ba
PR đang được review ngay lúc đó.

**Lối thoát.** `tal review-queue` nay trả `claimed` bên cạnh `eligible`, và phân biệt **ba**
trạng thái — đọc đúng cái nào trước khi kết luận:

| Trạng thái | Nghĩa | Việc phải làm |
|---|---|---|
| `hàng đợi rỗng THẬT` | đã đo, không có gì chờ | Kết thúc lượt là đúng |
| `đang bị session khác giữ` | có việc, nhưng không phải của bạn | **Đừng chờ**, đừng đụng vào ref. Mỗi dòng nêu tên chủ và lease còn bao lâu |
| `orphan: true` / `by: "?"` | ref không mang payload chủ | `tal gc` phân xử sau thời gian ân hạn. **Không bao giờ** xoá ref bằng tay — xoá nhầm một ref sống là đặt hai session lên cùng một PR |

## §10. `git push` bị từ chối non-fast-forward

**Triệu chứng.** Push trượt với non-fast-forward.

**Chẩn đoán.** Với nhiều session cùng chạy, `origin/<base>` tiến liên tục — hai PR khác có
thể merge trong lúc bạn đang commit.

**Lối thoát.**

```sh
git fetch && git rebase origin/<base>
```

Không `--force`. (`tal` push bằng `--force-with-lease` ở những chỗ nó tự push; đó là chuyện
khác với việc bạn tự ép một nhánh.)

## §11. Bảng mã thoát

| Mã | Nghĩa | Phản ứng đúng |
|---|---|---|
| 0 | xong | — |
| 2 | test ĐỎ thật, hoặc dùng lệnh sai / thiếu điều kiện | Đọc thông điệp: nó nói thiếu gì |
| 3 | **CỔNG HỎNG** (môi trường, cây tạm), hoặc không tìm thấy thẻ lease | §4, §7 — đừng đi tìm test hỏng |
| 4 | lease hỏng: HẾT / MẤT / FENCED / QUÁ HẠN | §3 — DỪNG mọi thao tác ghi |
| 5 | `adopt` từ chối: lease thuộc session khác | §4 — ca cần người |
| 75 | **BUSY** — người khác đang giữ. Không phải lỗi | Làm việc khác, hỏi lại lượt sau |
| khác 0 kèm `KHÔNG ĐO ĐƯỢC` | không đo được, ≠ rỗng | §8 — hỏi lại sau, đừng kết luận |

## §12. Lệnh can thiệp — đọc trước, ghi sau

```sh
tal status               # ai đang giữ gì, còn bao lâu
tal gc --dry-run         # sẽ dọn những gì, nếu chạy thật
tal assert               # mình có THẬT sự còn giữ lô này không
tal doctor               # môi trường, config đã giải, cảnh báo
tal config               # giá trị đã giải kèm NGUỒN của từng giá trị
```

Chỉ sau khi bốn lệnh đọc ở trên đã trả lời, mới tới lệnh ghi:

```sh
tal unlock <key> --force --note "lý do"    # can thiệp tay
tal requeue <N> --note "vì sao lần này khác"
```

`unlock --force` chỉ dùng khi bạn **chắc chắn** session giữ lease đã chết. Bình thường để
`tal gc` thu hồi theo TTL.

Biến môi trường điều chỉnh được: TTL, số lần thử tối đa, tên nhánh base/promotion, namespace
ref. **Đừng export biến session id** — một biến quên xoá gộp hai session thành một danh
tính, và `tal doctor` cảnh báo mỗi khi thấy nó được đặt. Giá trị mặc định và tên đầy đủ:
`tal config`.

---

## Nguồn — đoạn nào đến từ đâu

Lọc (không chép) từ tài liệu vòng lặp đang sống trong kho tiêu thụ `godx-jp/godx-tempo`,
nhánh `dev`. Mọi giả định của riêng kho đó đã bị nâng lên một bậc trừu tượng hoặc gỡ. Bảng
này để `godx-tempo#4147` biết cái gì đã sang plugin và có thể xoá ở kho tiêu thụ.

| Mục ở đây | Nguồn |
|---|---|
| §1 (session bị nhốt) | `docs/guide/agent-loop-skills.md` §5 (L310–412) |
| §2 (bị deny khi chạy test) | `docs/guide/agent-loop-skills.md` §5 + `.claude/agent-loop/test-policy.md` |
| §3 (`assert` mất lease) | `docs/guide/agent-loop-skills.md` §5 |
| §4 (mất thẻ ≠ mất lease) | `docs/guide/agent-loop-skills.md` §5 |
| §5 (dead-letter oan) | `docs/guide/agent-loop-skills.md` §5 |
| §6 (PR đóng mà không merge) | `docs/guide/agent-loop-skills.md` §5 |
| §7 (cổng hỏng ≠ test đỏ) | `docs/guide/agent-loop-skills.md` §5 |
| §8 (hàng đợi rỗng là phép đo) | `docs/guide/agent-issue-loop.md` L800–829 |
| §9 (hàng đợi review nói AI đang giữ) | `docs/guide/agent-issue-loop.md` L892–908 |
| §10 (base tiến lên trước bạn) | `docs/guide/agent-issue-loop.md` L795–798 |
| §11, §12 | `docs/guide/agent-issue-loop.md` L1291–1318 ("Incidents") + mã thoát đọc thẳng từ `bin/tal` |

**Đã BỎ, không dời** (mô tả lệnh đã gỡ hoặc hành vi cũ, đã kiểm bằng `tal <lệnh> --help`):

- *"`tal adopt` không còn tồn tại"* — sai với plugin: `tal adopt` **có**, và nó vẫn là lối
  thoát đúng cho §4.
- Đoạn dạy `git checkout <base> -- <đường dẫn tới tal>` để cập nhật công cụ — `tal` không
  còn là file được track.
- Đoạn nói full suite là một bước của cổng review — `merge-batch` nay mặc định **không**
  chạy full suite.
- Mọi mô tả rổ `orphans` / `humans` và khoá `agentLogins` của `review-queue` — đã bị gỡ
  trong bản gom lô.
