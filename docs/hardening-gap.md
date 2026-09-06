# Khoảng cách gia cố: `bin/tal` của plugin vs bản `tal` mà godx-tempo vừa gỡ

**Đo bằng máy, không phải cảm giác.** `tests/tal_test.py` là bộ test 142 nhóm từng sống
trong `godx-jp/godx-tempo` tại `.claude/tools/agent-loop/tal_test.py`, canh một bản `tal`
6951 dòng đã vá tới #2782. Kho đó vừa **xoá bản của mình** và chuyển sang dùng `bin/tal`
của plugin (2770 dòng).

Chạy đúng bộ test ấy lên `bin/tal`:

    XANH 4/46 nhóm · ĐỎ 42 nhóm · 137 khẳng định đỏ

Nghĩa là: vòng lặp ở godx-tempo đang chạy trên rào **yếu hơn hẳn** so với một tháng trước.
Không phải suy đoán — mỗi dòng dưới đây là một khẳng định có bài test đòi, và đang đỏ.

## Bốn thứ nặng nhất

| Rào đã mất | Hậu quả khi nó vắng |
|---|---|
| `ref_exists` phải **RAISE** khi quota cạn, không trả `False` | lỗi API đọc thành "không ai giữ lease" ⇒ **hai session cùng làm một issue** — đúng cái duy nhất cả hệ thống tồn tại để ngăn |
| `hook-guard` cho qua lệnh git **chỉ đọc** | chặn theo cwd ⇒ `pwd`, `cd`, `git status`, và cả `tal claim` mà thông điệp mách đều bị chặn ⇒ **session bị nhốt**, không lệnh nào tự gỡ được |
| `hook-guard` chặn `gh pr merge` khi CI **đỏ/chưa xong** | `gh pr merge` là đường duy nhất không có rào ⇒ merge một PR test đang đỏ |
| `gc` hỏi "còn nội dung chưa tới base" trước khi xoá | **xoá worktree/branch còn commit chưa merge** — mất code |

Cộng: `set_state_labels(preserve=)` (claim quét sạch nhãn review đã có), `release` từ chối
lease của người khác, `review-claim`/`verdict` từ chối PR đã merge/đóng (#2153), `gc` chừa
branch còn PR mở và issue đã mở lại, `remove_worktree` không khai thành công khi chưa xoá
được (#2177/#2710), `merge` đi qua rào `closable` và rào con trỏ dangling.

## Kiểm kê đầy đủ

### test_review_claim_runs_and_releases_on_error  (2 khẳng định)
  - lỗi giữa chừng → XOÁ ref khoá
  - lỗi giữa chừng → nhả cả khoá cục bộ

### test_released_lease_card  (6 khẳng định)
  - thẻ được đánh dấu released
  - epoch bị bỏ — fencing token cũ không còn giá trị
  - có mốc thời gian released_at
  - lease_file(search=False) vẫn trả thẻ đã released
  - do_assert báo đúng lý do

### test_hook_guard_not_a_trap  (31 khẳng định)
  - `pwd` trong worktree đã nhả lease → CHO QUA
  - `cd` ra ngoài → CHO QUA (không nhốt)
  - lệnh git chỉ đọc → CHO QUA: git status --porcelain
  - lệnh git chỉ đọc → CHO QUA: git log --oneline -5
  - lệnh git chỉ đọc → CHO QUA: git diff

### test_dead_letter_counts_failures  (1 khẳng định)
  - NỔ ValueError: substring not found

### test_remove_worktree_rmtrees  (2 khẳng định)
  - có xoá đã kiểm chứng — `remove --force` từ chối thì `prune` KHÔNG xoá thư mục (#2177: rmtree nhắm vào bản ĐÃ D
  - NỔ ValueError: substring not found

### test_remove_worktree_failure_keeps_registration  (4 khẳng định)
  - trả False — không khai 'đã dọn' cho việc chưa làm
  - KHÔNG chạy `git worktree prune` khi thư mục chưa dời/xoá được
  - dời được thì trả True
  - đường dẫn cũ hết tồn tại — prune từ đây là an toàn

### test_gc_spares_branch_with_open_pr  (3 khẳng định)
  - KHÔNG xoá branch đang có PR mở, dù PR cũ cùng branch đã merge
  - và nói rõ vì sao bỏ qua
  - không có lời gọi DELETE nào chạm branch được chừa

### test_merge_and_gc_close_through_the_same_gate  (3 khẳng định)
  - cmd_merge gọi `gh issue close`
  - cmd_merge đi qua rào closable, không đóng thẳng tay
  - NỔ ValueError: substring not found

### test_realign_checks_submodule_is_checked_out  (1 khẳng định)
  - NỔ ValueError: substring not found

### test_audit_blocks_child_pr_on_wrong_base  (3 khẳng định)
  - audit đọc base của PR con
  - có mã lỗi riêng cho base sai, không lẫn vào no-pr
  - so với branch của .gitmodules (want_base), không hard-code tên nhánh

### test_doctor_scans_for_dangling_pointers  (2 khẳng định)
  - có hàm quét riêng, gọi lại được
  - NỔ ValueError: substring not found

### test_claim_rollback_spares_adopted_refs  (3 khẳng định)
  - tách hai danh sách: ref vừa tạo vs ref nhận lại
  - rollback chỉ duyệt `created`
  - claim hỏi sổ khi ref đã tồn tại

### test_merge_gates_on_dangling_pointer  (2 khẳng định)
  - có hàm kiểm riêng, gọi lại được
  - NỔ ValueError: substring not found

### test_pr_merge_never_sets_review_label  (1 khẳng định)
  - NỔ ValueError: substring not found

### test_gc_spares_reopened_issue  (2 khẳng định)
  - có hàm reopened_after()
  - NỔ ValueError: substring not found

### test_queue_refuses_to_call_it_empty_when_it_could_not_measure  (1 khẳng định)
  - phải RAISE thay vì báo hàng đợi rỗng

### test_adopt_restores_the_card_without_bumping_epoch  (2 khẳng định)
  - thông điệp CHỈ ra đường phục hồi, không đẩy về claim
  - NỔ NameError: name '_AdoptArgs' is not defined

### test_adopt_refuses_a_lease_that_belongs_to_another_session  (1 khẳng định)
  - NỔ NameError: name '_AdoptArgs' is not defined

### test_adopt_refuses_when_the_lease_ref_is_already_gone  (1 khẳng định)
  - NỔ NameError: name '_AdoptArgs' is not defined

### test_a_newly_added_test_actually_runs  (1 khẳng định)
  - suite con ĐỎ và gọi ĐÚNG TÊN ca mới thêm — tức là ca đó đã thật sự chạy

### test_verdict_refuses_a_merged_pr  (7 khẳng định)
  - PR MERGED → Fail, không exit 0
  - thông điệp nói rõ: verdict vô nghĩa, mở issue mới cho điểm blocking
  - KHÔNG ghi comment verdict lên PR
  - KHÔNG ghi sổ — giữ nguyên trạng thái mà merge đã ghi
  - KHÔNG dán nhãn changes-requested lên issue đã khép

### test_ref_create_wraps_payload_in_a_tag_object  (1 khẳng định)
  - NỔ TypeError: ref_create() takes 2 positional arguments but 3 were given

### test_review_claim_stamps_owner_payload_on_the_ref  (3 khẳng định)
  - payload mang session THẬT của người claim
  - payload đủ host/pid/hạn — status in được 'ai giữ, còn bao lâu'
  - PR đã MERGED → review-claim từ chối ngay (#2153)

### test_unlock_pr_requires_note  (3 khẳng định)
  - cmd_unlock kiểm pr-* và đòi note
  - ghi comment lên PR khi unlock pr-*
  - unlock pr-* không note phải FAIL

### test_verdict_resets_issue_when_pr_closed_without_merge  (3 khẳng định)
  - nói rõ issue đã trả về hàng đợi
  - ghi sổ lý do
  - gắn lại ready, gỡ awaiting-review

### test_verdict_skips_reset_when_issue_shipped  (3 khẳng định)
  - vẫn từ chối verdict trên PR đóng
  - không gắn lại ready
  - ghi sổ bỏ qua

### test_2300_ref_exists_three_states  (1 khẳng định)
  - quota cạn phải RAISE, không phải False

### test_2300_ref_delete_reports  (3 khẳng định)
  - ref vốn không tồn tại → True (đã mất)
  - xoá fail thật → False
  - và warn nói to

### test_2300_set_state_labels_safe_and_preserve  (3 khẳng định)
  - GET fail → KHÔNG PUT
  - warn nói rõ vì sao bỏ
  - NỔ TypeError: set_state_labels() got an unexpected keyword argument 'preserve'

### test_2300_release_refuses_foreign_and_cwd_mismatch  (3 khẳng định)
  - KHÔNG được ghi sổ khi từ chối
  - phải từ chối
  - lệch thẻ/tham số phải DỪNG

### test_2300_requeue_contract  (1 khẳng định)
  - gắn lại agent:ready

### test_2300_gc_keeps_unpushed_commits  (2 khẳng định)
  - gc hỏi 'còn nội dung nào chưa tới base'
  - NỔ ValueError: substring not found

### test_2993_gc_abandoned_refuses_when_branch_still_carries_content  (1 khẳng định)
  - NỔ Fail: không suy ra được owner/repo từ remote:

### test_2993_gc_abandoned_still_deletes_a_branch_that_holds_nothing  (1 khẳng định)
  - NỔ Fail: không suy ra được owner/repo từ remote:

### test_config_surface_is_wired_not_decorative  (2 khẳng định)
  - baseBranch từ config
  - NỔ AttributeError: module 'tal' has no attribute 'PROMOTION_BRANCH'

### test_config_command_exists_and_reports_sources  (4 khẳng định)
  - tal config --json có `values`
  - tal config --json có `sources`
  - tal config --json có `riskDomains`
  - NỔ KeyError: 'sources'

### test_status_table_carries_addr_column  (3 khẳng định)
  - header của `tal status` có cột addr
  - dòng in của `tal status` đọc addr từ mỗi hàng
  - cả lease issue LẪN lease review đều ghi agent_pid

### test_review_queue_reports_humans_separately  (3 khẳng định)
  - JSON có khoá `humans` — người gọi máy đọc được, không phải chỉ in ra
  - phân rổ đi qua hàm thuần đã test hai chiều, không so chuỗi tại chỗ
  - `humans` KHÔNG chặn câu 'rỗng THẬT' — PR của người không phải việc của vòng lặp, còn nó mà báo hết việc là ĐÚN

### test_config_prints_agent_logins  (3 khẳng định)
  - nhánh --json có khoá `agentLogins` (giá trị ĐÃ phân giải, không phải raw)
  - nhánh in cho người cũng có, kèm số lượng
  - rỗng thì nói rõ hệ quả, đừng in một dòng trống để người đọc tự đoán (dùng [1:2]/len chứ không [1] — khối biến 

### test_2782_gc_fetches_origin_base_before_measuring  (2 khẳng định)
  - cmd_gc fetch origin/<base> trước khi đo
  - NỔ ValueError: substring not found

### test_2710_remove_worktree_does_not_claim_success_when_branch_remains  (3 khẳng định)
  - thất bại xoá branch/worktree phải nói ra, không nuốt stderr
  - xoá theo đường dẫn git worktree list, không chỉ `.claude/worktrees/`
  - xoá branch bằng -D (không -d so HEAD cây chính)

### test_hook_guard_command_patterns_run_without_a_lease  (10 khẳng định)
  - git push origin dev NGOÀI lease → CHẶN
  - git push origin main NGOÀI lease → CHẶN
  - lenh THAT van CHAN
  - lenh THAT dung SAU heredoc da dong → van CHAN (khong nuot qua tay)
  - merge PR có check ĐỎ → CHẶN

## Đọc bộ test này thế nào

Nó **cố ý ĐỎ**. Một bộ test xanh nhờ xoá bớt bài là đúng thứ mà chính kho gốc gọi tên:
*"một bài test tồn tại, trông như đã canh, và không bao giờ nổ thì TỆ HƠN không có test —
nó trả lời 'rồi' cho câu hỏi 'chỗ này canh chưa?'"*. Nên ở đây không bài nào bị gỡ để lấy
màu xanh; suite đỏ đúng bằng khoảng cách thật.

## Hướng đề xuất

Không port từng mảnh. `bin/tal` của plugin nên **trở thành** bản đã gia cố (6951 dòng +
mô hình LÔ + bộ test), thay vì bản rút gọn. Như vậy vừa giữ được một-nguồn-sự-thật (không
còn hai `refNamespace` song song — lý do chính đáng để godx-tempo gỡ bản của nó), vừa
không mất rào nào. Nội dung ấy **đã tồn tại**: nhánh `agent-loop-batch-model` của
godx-tempo (PR #4141) chính là bản gia cố đã mang mô hình lô.
