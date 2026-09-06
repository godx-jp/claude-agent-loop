# Hướng dẫn cho repo dùng agent-loop

Dành cho người dựng vòng lặp trong **repo của bạn**. Plugin mang **cơ chế**; repo mang
**chính sách**. Không khai chính sách thì vòng lặp chạy được nhưng mù — nó không biết repo
bạn chạy test thế nào, quy ước gì, đã cháy ở đâu.

Đọc `README.md` trước để hiểu *vì sao* mô hình là lô. File này là *làm thế nào*.

---

## 0. Điều kiện

| Cần | Vì sao |
|---|---|
| `git`, `gh` đã `gh auth login`, `python3` (stdlib) | tal không dùng `jq`, không dùng `flock` |
| Repo trên GitHub, có `baseBranch` (vd `dev`) và `promotionBranch` (vd `main`) | lô vào base; full suite ở PR base→promotion |
| GitHub Issues bật | ledger sống trong comment của issue |
| CI chạy được trên PR | `tal merge` đòi CI của chính PR đó xanh |

Quyền `gh` phải tạo được ref tuỳ ý (`POST /git/refs`). `tal doctor` kiểm điều này bằng một
ref thử — nếu nó đỏ thì **đừng chạy nhiều session**, khoá không có hiệu lực.

---

## 0b. Ranh giới: plugin mang CƠ CHẾ, repo mang CHÍNH SÁCH

Đây là luật quyết định mọi tranh cãi về "cái này để đâu". Hỏi đúng một câu, cho
TỪNG ĐOẠN — không phải từng file:

> **Câu này còn đúng ở một kho stack khác không?**

| Đúng ⇒ thuộc **plugin** | Không ⇒ thuộc **repo bạn** |
|---|---|
| lease, fencing, hàng đợi, gc, luật tên nhánh | lệnh test theo vùng (`affectedTests`) |
| hai vai code/review và ranh giới giữa chúng | lệnh "chạy tất" (`fullSuite`) |
| cạm bẫy chung: `cd` không phải rào, merge PR của chính mình | bẫy của ngôn ngữ/framework bạn dùng |
| runbook sự cố: session bị nhốt, lease mồ côi | bản đồ code→doc (`docsRules`) |
| Conventional Comments, mức độ chặn merge | vùng rủi ro cao của nghiệp vụ |

**Repo bạn KHÔNG nên có**: bản sao `tal`, skill vòng lặp riêng, tài liệu giải
thích `tal` hoạt động thế nào. Có những thứ đó nghĩa là bạn đang bảo trì một
nhánh rẽ, và nó sẽ trôi khỏi bản chính mà không ai thấy.

Repo bạn **nên** có đúng bốn thứ: `.claude/agent-loop.json`, ba `policyDocs` chỉ
chứa phần riêng của stack, workflow CI, và nhãn `agent:ready` do người gắn.

### Sai chiều nào cũng hỏng

Đẩy phần riêng của repo lên plugin là lỗi ngược lại, và nó **tệ hơn**: plugin sẽ
mang giả định của một kho sang mọi kho khác. Đã trả giá — một hằng số từng ghim
cứng `dev|main`, nên rào chặn push-thẳng **im lặng không đóng** ở mọi repo đặt
tên nhánh khác. Một rào im lặng không đóng tệ hơn không có rào.

---

---

## 1. Cài

```sh
/plugin marketplace add godx-jp/claude-agent-loop
/plugin install agent-loop@godx
/reload-plugins
```

Trong repo:

```sh
cp <plugin>/examples/agent-loop.json .claude/agent-loop.json
$EDITOR .claude/agent-loop.json          # bước 2
printf '.claude/worktrees/\n.tal-lease.json\n' >> .gitignore
tal doctor --fix                          # tạo nhãn agent:*, bật delete_branch_on_merge
tal config                                # đọc lại chính sách đã giải
```

`.claude/agent-loop.json` **phải commit** — nó là chính sách chung của cả đội, không phải
cấu hình máy cá nhân.

---

## 2. `.claude/agent-loop.json` — từng khoá

### Bắt buộc trên thực tế

| Khoá | Không khai thì sao |
|---|---|
| `baseBranch` | mặc định `"dev"`. Sai là mọi PR nhắm sai nhánh |
| `promotionBranch` | mặc định `"main"`. `tal release-to-main` mở PR vào đây. Tên cũ `mainBranch` vẫn được đọc |
| **`refNamespace`** | mặc định `"refs/agent-loop/leases/"`. **Chỉ đổi khi bạn hiểu hệ quả:** hai bản `tal` chạy trên cùng repo với hai namespace khác nhau là hai tập lease **không thấy nhau**, tức mất hẳn loại trừ tương hỗ — đúng thứ duy nhất công cụ này tồn tại để bảo đảm. Không có env nào đè được nó, có chủ ý |
| **`affectedTests`** | **`tal tests` không suy ra được lệnh nào — vai code mất hẳn cách chạy test đúng phạm vi.** Đây là khoá quan trọng nhất |
| `fullSuite` | `tal fullsuite` không chạy được, và **`hook-guard` không có gì để chặn** — full suite lọt vào vòng lặp |
| `policyDocs` | skill chỉ có luật chung, không biết quy ước repo |

### Tuỳ chọn, nhưng nên khai

| Khoá | Việc |
|---|---|
| `setup` / `setupVerify` | lệnh dựng môi trường trong cây tạm của `tal merge-batch`, và kiểm rẻ tiền chứng minh nó đã dựng xong. Không khai thì cổng gom lô đỏ 100% vì thiếu `vendor/`, `node_modules/`, `.env` — **cổng hỏng**, không phải test đỏ |
| `agentLogins` | tài khoản GitHub mà session agent đẩy PR qua. Không khai thì `review-queue` xếp **PR của người** vào rổ mồ côi, và một session có thể ghi verdict lên việc họ đang làm |
| `riskDomains` | đường dẫn mà diff chạm vào thì review phải ở tier cao nhất. `tal config` in ra cho skill đọc |
| `formatCmd` | lệnh format của repo, để skill gọi đúng thay vì đoán |

### `affectedTests` — viết cho đúng

Đây là [Test Impact Analysis](https://dora.dev/capabilities/test-automation/): đường dẫn
nào đổi thì chạy lệnh test nào. Cấu trúc:

```json
"affectedTests": [
  {
    "when": "<regex khớp đường dẫn file>",
    "run": ["<lệnh>", "<lệnh>"],
    "why": "<vì sao — cho người đọc, tal không dùng>"
  }
]
```

Cách tal dùng: lấy `git diff --name-only origin/<base>...HEAD` cộng file chưa commit, chạy
từng `when` lên danh sách đó, gộp mọi `run` khớp được (bỏ trùng, giữ thứ tự), rồi in ra
hoặc chạy với `--run`.

**Ba luật khi viết:**

1. **Lệnh phải HẸP.** Theo filter, theo thư mục, theo package — không bao giờ là toàn bộ
   suite. Nếu một luật của bạn chạy hết mọi test thì bạn vừa đưa full suite trở lại vòng
   lặp bằng cửa sau.
2. **Đi từ hẹp đến rộng.** Luật `^lang/` (chỉ chuỗi hiển thị) nên chạy ít hơn hẳn luật
   `^backend/app/`. Một sửa text chỉ nên kích hoạt đúng một lệnh nhanh.
3. **Có ít nhất một luật bắt trọn.** Ví dụ `\\.tsx?$` → `typecheck`. Đường dẫn không khớp
   luật nào thì `tal tests` in "không có test liên quan" và vai code sẽ ship mà không chạy
   gì — đôi khi đúng (đổi ảnh, đổi README), nhưng phải là quyết định của bạn chứ không
   phải khoảng trống.

Ví dụ thật (Laravel + React):

```json
"affectedTests": [
  { "when": "^lang/|^resources/js/locales/",
    "run": ["pnpm test -- --run i18n"],
    "why": "chuỗi hiển thị: một lệnh nhanh là đủ" },

  { "when": "^backend/app/Billing/|^backend/app/Payments/",
    "run": ["cd backend && vendor/bin/pest --compact --filter='Billing|Payment'"],
    "why": "tiền: chạy trọn nhóm test của tầng, không chỉ file bị sửa" },

  { "when": "^backend/app/",
    "run": ["cd backend && vendor/bin/pest --compact --group=unit"],
    "why": "code PHP nói chung" },

  { "when": "^backend/database/migrations/",
    "run": ["cd backend && vendor/bin/pest --compact --group=migration"],
    "why": "DDL phải chạy trên engine thật, không chỉ SQLite" },

  { "when": "\\.tsx?$",
    "run": ["pnpm typecheck"],
    "why": "rào rẻ nhất cho mọi thay đổi TS" }
]
```

Kiểm luật bạn vừa viết, không đoán:

```sh
tal tests --pr 123          # in đúng những lệnh sẽ chạy cho diff của PR 123
```

### `fullSuite` — và vì sao khai nó lại là để CẤM nó

```json
"fullSuite": [
  "cd backend && php -d memory_limit=-1 vendor/bin/pest --compact",
  "pnpm typecheck"
]
```

**Bẫy phải tránh khi khai — phát hiện lúc dựng config thật cho godx-task:**

> `hook-guard` so khớp **substring**. Nếu bạn khai `fullSuite: ["php artisan test --compact"]`
> thì mọi lệnh trong `affectedTests` có chứa chuỗi đó — kể cả
> `php artisan test --compact --testsuite=Unit` — **đều bị chặn**. Vòng lặp mất luôn cách
> chạy test hẹp, tức là bạn vừa khoá chính cái đường thoát mà mô hình này dựa vào.
>
> Khai **script "chạy tất" của repo** thay vì lệnh chạy test trần: `composer ci:check`,
> `make ci`, `pnpm test:all`. Chúng không phải tiền tố của lệnh hẹp nào.
>
> Kiểm bằng máy, đừng đọc bằng mắt:
>
> ```sh
> python3 - <<'EOF'
> import json; d=json.load(open('.claude/agent-loop.json'))
> aff=[c for r in d['affectedTests'] for c in r['run']]
> bad=[(f,c) for f in d['fullSuite'] for c in aff if f in c]
> print("ĐỤNG:",bad) if bad else print(f"OK — {len(aff)} lệnh affectedTests không bị chặn nhầm")
> EOF
> ```

Khai xong, ba thứ xảy ra:

1. `tal fullsuite` chạy được (từ gốc repo, không phải trong worktree).
2. `tal release-to-main` nhắc rằng đây là nơi chúng chạy trong CI.
3. **`hook-guard` chặn đúng những chuỗi này** nếu agent gõ chúng trong worktree của vòng
   lặp. So khớp là **substring trên chuỗi bạn khai** — nên khai đúng lệnh thật, đừng khai
   một biến thể gần đúng, kẻo rào không đóng.

Kiểm rào:

```sh
cd .claude/worktrees/batch-*        # bất kỳ worktree nào của lô
# rồi bảo agent chạy full suite — nó phải bị deny với thông điệp của tal
```

### `batch`

```json
"batch": { "min": 10, "max": 20 }
```

`min` là số issue tối thiểu để lập lô. Dưới mức đó `tal batch claim` trả **exit 75** và
không lập lô — cố ý: lô nhỏ là quay lại đúng cái đang phải chữa. Backlog thưa thì hoặc gắn
thêm nhãn `ready`, hoặc chạy `tal batch claim --min 5` khi bạn chấp nhận.

Đừng đặt `max` quá lớn. Trần thật không phải kỹ thuật mà là **review**: một PR mà session
review không đọc nổi trong một lượt thì review thành đóng dấu. 20 là mức đã cân; hơn nữa
thì tự đo trước.

### `policyDocs`

Ba file trong repo, skill **bắt buộc** đọc:

| Khoá | Đặt gì vào |
|---|---|
| `work` | thứ tự lệnh bắt buộc, codegen, cạm bẫy đã biết, thư mục nào không được đụng |
| `test` | cách chạy test theo vùng bằng lời (bổ sung cho `affectedTests`), test nào chậm, test nào cần service ngoài |
| `review` | checklist riêng: chỗ đã từng cháy, quy ước bắt buộc, luật domain (tiền, thời gian, quyền) |

Không có chúng, skill vẫn chạy nhưng chỉ có luật chung — và **nói ra rằng nó đang thiếu**.

### `labels`

Bốn nhãn đầu (`working` / `reviewing` / `blocked` / `shipped`) khai **đúng tên repo bạn
đang dùng**, để bảng issue không bị chẻ làm hai hệ. Không dùng thì để `""`. Năm nhãn
`agent:*` do plugin sở hữu, `tal doctor --fix` tự tạo.

### `docsRules` / `docsGenericRules`

`tal docs-check <PR>` là **gợi ý cho reviewer**, không phải rào.

```json
"docsRules": [
  { "when": "BusinessClock|business_day", "expect": ["docs/guide/business-time.md"],
    "why": "thời gian nghiệp vụ theo timezone chi nhánh" }
],
"docsGenericRules": [
  { "when": "^backend/routes/|Controllers/", "expectPrefix": "backend/storage/api-docs/",
    "why": "chạm route/controller nhưng không regen tài liệu API" }
]
```

Lấy `docsRules` từ chính những dòng "Tracked in `<doc>`" mà tài liệu repo tự tuyên bố —
đừng tự nghĩ ra. `docsGenericRules` mặc định **rỗng**: một luật gắn cứng đường dẫn của repo
khác là phát biểu sai ở repo bạn, và một phát biểu sai còn tệ hơn im lặng.

---

## 3. CI — hai workflow, không hơn

Đây là phần plugin **không** mang hộ được, và thiếu nó thì `tal merge` sẽ chặn với lý do
"không thấy CI nào — không có đối chứng để merge".

### A. PR vào base: chỉ test liên quan

`.github/workflows/pr-affected.yml`

```yaml
name: PR checks
on:
  pull_request:
    branches: [dev]          # = baseBranch

concurrency:
  group: pr-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  affected:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }         # tal cần lịch sử để diff với base

      - uses: actions/checkout@v4        # một nguồn sự thật cho tal, không vendor bản sao
        with:
          repository: godx-jp/claude-agent-loop
          path: .agent-loop

      # ... setup ngôn ngữ + cài dependency của repo bạn ...

      - name: Test liên quan
        env:
          GH_TOKEN: ${{ github.token }}
        run: python3 .agent-loop/bin/tal tests --pr ${{ github.event.pull_request.number }} --run
```

Một job, một tên check. `tal merge` đọc `gh pr checks` và chặn khi **fail** hoặc
**pending** — nên đừng để job nào treo vô hạn.

### B. PR vào main: full suite, một lần mỗi chu kỳ release

`.github/workflows/release-full-suite.yml`

```yaml
name: Full suite
on:
  pull_request:
    branches: [main]         # = promotionBranch
  workflow_dispatch:

jobs:
  full-suite:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/checkout@v4
        with:
          repository: godx-jp/claude-agent-loop
          path: .agent-loop

      # ... setup + dependency + service (DB thật, không SQLite) ...

      - name: Full suite
        run: python3 .agent-loop/bin/tal fullsuite
```

`tal fullsuite` từ chối chạy khi cwd nằm trong `.claude/worktrees/` — trong CI thì không
nên có, nên nó chạy bình thường. Đây là **nơi duy nhất** full suite chạy tự động.

### Branch protection

| Nhánh | Bật gì |
|---|---|
| `dev` (base) | required status check = job của workflow A · cấm push thẳng |
| `main` | required status check = job của workflow B · cấm push thẳng · yêu cầu người duyệt |

`hook-guard` đã chặn agent push thẳng vào base/main, nhưng branch protection là tầng chặn
duy nhất không phụ thuộc việc agent có chạy qua hook hay không.

### C. Cổng chống-xoá-file cho lượt promote — nửa mà plugin KHÔNG phủ được

`tal merge --promote` từ chối merge PR `base → promotion` nếu nhánh phát hành có file mà
nhánh nguồn không có (hotfix vá thẳng lên production, chưa quay ngược về base). Nhưng rào
đó chỉ phủ **đường `tal`**. Người gõ `gh pr merge` hay bấm nút trên web thì không đi qua
nó, và hai lượt promote gần nhất ở kho đã đo được đều đi đường sau.

Nên nửa còn lại phải sống ở CI của **bạn**: một workflow chạy trên PR có
`head_ref == <baseBranch>`, không bị `paths:` lọc (rào này phát biểu về file **không** nằm
trong diff, tức đúng thứ bộ lọc theo path không nhìn thấy), đo đúng chiều
`origin/<base>..origin/<promotion>` với `--diff-filter=A --no-renames -z`. Đảo chiều hay bỏ
một cờ đều làm cổng **im lặng báo sạch**, và một cổng báo sạch nguy hiểm hơn một cổng không
tồn tại.

---

## 4. Chạy hằng ngày

Mở cổng cho bot bằng nhãn `agent:ready` trên issue. Không có nhãn đó thì bot bỏ qua — để
không session nào hồn nhiên bắt tay vào một epic kiến trúc.

Hai session Claude Code **khác nhau**:

```
/loop /agent-loop:batch-work       # session code
/loop /agent-loop:batch-review     # session review
```

Tách vai dựa trên `CLAUDE_CODE_SESSION_ID`. Thiếu biến đó thì rào "review phải khác session
code" rơi về `shell-<host>-<ppid>` và yếu đi — `tal doctor` cảnh báo.

Một lượt code trông như:

```
tal gc → tal batch claim  →  12 issue, worktree .claude/worktrees/batch-20260906-1430
  với mỗi issue: đọc comment + kiểm origin → sửa → commit "fix(scope): … (#1234)"
tal batch status  →  issue nào chưa có commit, commit nào lạc
tal tests --run   →  4 lệnh test liên quan, xanh
tal pr            →  1 PR, Closes #… × 12, nhả lease
```

Một lượt review:

```
tal gc → tal review-queue → tal review-claim <PR>
đọc diff theo từng issue → tal tests --pr <PR> → tal review-verdict <PR> pass
tal merge <PR>            # review đạt + CI xanh, hai cổng cưỡng chế bằng máy
```

Khi base tích đủ, mở cổng ra production:

```sh
tal release-to-main       # PR dev→main; full suite chạy ở CI của PR này
```

---

## 5. Hai ca đặc biệt

### Issue chạm submodule

**Không đi đường lô.** Pointer submodule là sha trơ, nên nhánh chạm nó phải mang số issue
trong tên — mà tên lô thì không mang được. `tal pr` chặn lô chạm submodule.

```sh
tal batch drop <N> --reason "chạm submodule"
tal claim <N>             # branch issue-<N>
```

rồi làm theo skill `issue-submodule`.

### Một issue làm hỏng cả lô

```sh
tal batch drop <N> --reason "test đỏ, chưa gỡ được"          # trả về hàng đợi
tal batch drop <N> --blocked --reason "chờ ops mở port"      # đánh dấu blocked
```

Nó revert đúng những commit mang `(#N)`, gỡ `Closes #N` khỏi thân PR, và 11 issue kia đi
tiếp. Đây là lý do luật "mỗi commit mang `(#N)`" là **rào cứng** chứ không phải quy ước:
`tal pr` từ chối mở PR nếu còn commit không map được về đúng một issue.

---

## 6. Đọc lỗi

| Exit | Nghĩa | Làm gì |
|---|---|---|
| `75` | **không phải lỗi** — người khác đang giữ, hoặc chưa đủ `min` issue | nói rõ, kết thúc lượt |
| `5` | PR do chính session này code | chọn PR khác, **đừng** `--allow-self` |
| `4` | fencing: hết lease / mất lease / epoch lệch / quá hạn | **DỪNG mọi thao tác ghi**, đừng push |
| `3` | không tìm thấy thẻ lease, hoặc session giữ nhiều worktree | `cd` vào đúng worktree |
| `2` | vi phạm chính sách (commit lạc, issue rỗng, lô chạm submodule, thiếu config) | sửa đúng thứ nó nêu; **đừng** dùng cờ `--allow-*` để lách |

Tình huống hay gặp:

| Triệu chứng | Nguyên nhân |
|---|---|
| `tal merge` nói "không thấy CI nào" | chưa có workflow A, hoặc job không chạy trên PR đó |
| `tal tests` in "chưa khai affectedTests" | thiếu khoá quan trọng nhất — quay lại mục 2 |
| `tal pr` chặn vì "commit không map được" | tiêu đề commit thiếu `(#N)`, hoặc nhắc hai issue cùng lúc |
| `tal batch claim` luôn exit 75 | backlog thiếu nhãn `agent:ready`, hoặc `batch.min` quá cao |
| Agent bị deny khi chạy test | lệnh đó trùng chuỗi trong `fullSuite` — nó đúng là full suite |
| Lease "quá hạn" liên tục | thiếu `tal renew` giữa các bước dài, hoặc `ttlSeconds` quá ngắn |
| Mất `.tal-lease.json` mà lease vẫn sống | `tal adopt [N]` dựng lại thẻ từ sổ, **không** bump epoch |
| Issue dính `agent:dead-letter` | `tal requeue <N> --note "vì sao lần này khác"` — đường chính danh, giữ sử liệu |
| Vòng review thứ hai phải đọc lại cả lô | `tal review-delta <PR>` in đúng phần mới kể từ verdict trước |
| Hai issue khác nhau đụng cùng thư mục | `tal claim <N> --region <path>` giữ vùng file; chồng lấn với lease sống khác thì bị từ chối |

---

## 7. Nếu bạn đang dùng bản cũ (mỗi issue một vòng)

| Cũ | Mới |
|---|---|
| `/loop /agent-loop:issue-work` | `/loop /agent-loop:batch-work` |
| `/loop /agent-loop:issue-review` | `/loop /agent-loop:batch-review` |
| `tal claim <N>` cho mọi issue | `tal batch claim` — `tal claim` chỉ còn cho ca submodule |
| `tal merge-batch` mỗi vòng | vẫn còn, nhưng **đổi vai**: nó gom nhiều PR đã review đạt vào một cây tạm để chứng minh chúng đi cùng nhau được. Mặc định **không** chạy full suite (`--suite` mới chạy) |
| `fullSuite` chạy ở cổng review | chỉ ở CI của PR vào main, hoặc `tal fullsuite` |
| — | thêm `affectedTests`, `promotionBranch`, `batch`, `setup`/`setupVerify` vào config |

Lease, ledger, nhãn và worktree cũ vẫn đọc được — không cần dọn tay. Chạy `tal gc` một lượt
rồi `tal doctor` để xem còn thiếu gì.

---

## 8. Plugin KHÔNG làm gì

Nói rõ để không ai chờ nhầm:

- **Không** biết repo bạn chạy test thế nào — đó là `affectedTests` + `policyDocs.test`.
- **Không** viết workflow CI hộ bạn — mục 3.
- **Không** quyết issue nào đáng làm — đó là nhãn `agent:ready` do người gắn.
- **Không** merge khi thiếu một trong hai cổng (review đạt, CI xanh), và không có đường vòng
  nào ngoài `--force` do người gõ.
- **Không** chạy full suite. Không bao giờ, trong vòng lặp.

---

## 9. Chạy nhiều máy — ghim phiên bản, nếu không khoá vô nghĩa

`tal` là một **khoá phân tán**. Toàn bộ giá trị của nó nằm ở chỗ mọi session
đồng ý với nhau về "ai đang giữ gì". Hai máy cài hai bản `tal` khác nhau thì:

- mặc định khác `refNamespace` ⇒ **hai session không thấy lease của nhau** ⇒
  cùng làm một issue — đúng cái duy nhất hệ thống tồn tại để ngăn;
- khác cách đọc `fullSuite`/`affectedTests` ⇒ rào chặn khác nhau ở hai chỗ;
- khác hành vi `gc` ⇒ một máy xoá thứ máy kia còn cần.

Plugin cố ý **không có trường `version`** — nó dùng commit SHA làm phiên bản.
Nên repo bạn phải tự ghi SHA đang dùng, ở **một** chỗ, và có một phép kiểm kêu
khi lệch. Ghim `main` là không ghim gì: `main` di chuyển, và đã từng bị
force-push một lần.

Phép kiểm phải chứng minh **cả hai chiều**: xanh khi khớp, **và đỏ khi lệch**.
Một rào chỉ biết kêu mà không chứng minh được nó biết im thì sẽ bị tắt, và lúc
đó mất luôn phần canh đúng.

---

## 10. Khi nào KHÔNG nên dùng

Nói trước để khỏi mất thời gian:

| Tình huống | Vì sao không hợp |
|---|---|
| Một người, một session | Toàn bộ chi phí lease/fencing/worktree không mua được gì. Dùng git bình thường. |
| Backlog dưới ~10 issue `ready` mỗi đợt | Lô không đủ lớn để nuốt chi phí một vòng — quay lại đúng cái mô hình lô sinh ra để chữa. |
| Repo không dùng GitHub Issues | Ledger sống trong comment của issue. Không có issue thì không có sổ. |
| `gh` không tạo được ref tuỳ ý | Không có compare-and-swap thật ⇒ **không có khoá**. `tal doctor` kiểm điều này; nó đỏ thì đừng chạy nhiều session. |
| Việc cần một người quyết ở giữa chừng | Vòng lặp tối ưu cho việc chạy hết không cần hỏi. Việc cần hỏi thì mở issue cho người. |

---

## 11. Nhiều repo và submodule

Lô **không được chạm submodule** — pointer submodule là một sha trơ, không mang
thông tin, nên nhánh chạm nó phải mang số issue trong TÊN để tra ngược được "sha
này ra từ PR nào". Tên lô không mang được số issue nào.

Gặp trong lô thì gỡ ra rồi làm riêng:

```sh
tal batch drop <N> --reason "chạm submodule"
tal claim <N>          # nhánh issue-<số>, ở cả repo chính và repo con
```

Plugin **không** điều phối được nhiều repo ngang hàng (không phải submodule).
Hai repo song song là hai backlog, hai `refNamespace`, hai vòng lặp — và nếu một
thay đổi phải đi qua cả hai thì phần nối vẫn là việc của người.
