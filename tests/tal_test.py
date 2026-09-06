#!/usr/bin/env python3
"""Test cho `bin/tal` của plugin agent-loop.

Chạy: `python3 tests/tal_test.py`   (không cần pytest, không cần mạng)

Vì sao có file này: `tal` trước nay **không có test nào**, và cả bốn lỗi của #1342 đều
thuộc loại *lệnh vẫn exit 0, chỉ là không làm gì* — đúng loại mà chỉ test mới bắt được,
không phải đọc code. Test ở đây gọi thẳng hàm thật, chỉ thay `gh()` bằng bản ghi lại lời
gọi, nên nó kiểm hành vi chứ không kiểm lại chính nó.

Không đụng mạng, không đụng GitHub, không cần lease.
"""

import argparse
import importlib.machinery   # `import importlib.util` KHÔNG kéo theo cái này (3.14 → AttributeError)
import importlib.util
import json
import os
import re
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAL_SRC = HERE.parent / "bin" / "tal"   # bài đọc mã nguồn trỏ vào đây


def load_tal():
    spec = importlib.util.spec_from_loader("tal", importlib.machinery.SourceFileLoader("tal", str(HERE.parent / "bin" / "tal")))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tal"] = mod
    spec.loader.exec_module(mod)
    return mod


tal = load_tal()

# Bản gốc của những hàm bị test monkeypatch. Không có cái này thì một test thay
# `tal.lease_file` rồi bỏ đó sẽ làm test SAU đọc nhầm — và nó đã xảy ra: test guard
# của #1382 đỏ oan vì đọc phải thẻ lease do test #1342 để lại, trong khi guard hoàn
# toàn đúng khi chạy riêng. Test rò trạng thái thì không kiểm cái nó tưởng.
#
# Đây từng là DANH SÁCH TAY, và danh sách tay thì tụt lại: `do_assert`, `lease_expired`,
# `refs_all`, `docs_gate`… bị test thay mà không có trong danh sách, nên không được
# khôi phục. Hậu quả tệ hơn "đỏ oan" một bậc — nó XANH oan: test #1751 khẳng định
# `assert` cho cùng kết quả ở gốc worktree và trong submodule vẫn "ok" ngay cả khi
# đã GỠ bản sửa, vì `tal.do_assert` lúc đó là con rối của test trước trả về hằng số.
# Một phép đo xanh mà không đo gì là loại rào tệ hơn không có rào. Nên giờ chụp TOÀN
# BỘ hàm cấp module: thêm test mới không cần nhớ cập nhật danh sách nào.
REAL = {name: obj for name, obj in vars(tal).items()
        if isinstance(obj, types.FunctionType) or name == "C"}


def restore_tal():
    for name, fn in REAL.items():
        setattr(tal, name, fn)


FAILURES: list[str] = []


def check(cond: bool, label: str, detail: str = ""):
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}" + (f"\n       {detail}" if detail else ""))
        FAILURES.append(label)


def test_review_claim_runs_and_releases_on_error():
    """Hai thứ mà test cũ không chạm: đường THÀNH CÔNG của `cmd_review_claim`,
    và cái xảy ra khi có lỗi SAU khi đã giành khoá.

    Bộ test cũ chỉ gọi `assert_not_own_work` (rào tách vai) rồi dừng, nên một
    `NameError` ở ngay dòng sau cái rào sống sót qua toàn bộ suite: **mọi** lần
    gọi `review-claim` đều chết, và mỗi lần để lại `refs/tempo/leases/pr-<N>`
    không có chủ — `tal status` in session `?` cho tới hết TTL, hai session sau
    nhận `BUSY` thay vì nhận lỗi thật.
    """
    print("cmd_review_claim (#1616: chạy được + lỗi giữa chừng thì nhả khoá)")

    ledger = {"issue": 77, "group": [77], "state": "review", "review_rounds": 1,
              "sub_prs": {}, "history": []}
    notes: list[str] = []
    refs_made: list[str] = []
    refs_deleted: list[str] = []
    unlocks: list[str] = []

    def wire(gh_impl):
        tal.pr_issue = lambda pr: 77
        tal.ledger_read = lambda issue: (json.loads(json.dumps(ledger)), 1, tal.now())
        tal.ledger_write = lambda led, cid, note: notes.append(note)
        tal.local_lock = lambda key: True
        tal.local_unlock = lambda key: unlocks.append(key)
        # #2153: claim giờ đọc state PR trước; #2172: ref_create nhận payload chủ lease.
        tal.gh_json = lambda args, default=None: {"state": "OPEN"}
        tal.ref_create = lambda key, sha, payload=None: (refs_made.append(key), True)[1]
        tal.ref_delete = lambda key: refs_deleted.append(key)
        tal.head_sha = lambda: "deadbeef0000"
        tal.session_id = lambda: "revw9999zzzz"
        tal.gh = gh_impl

    def gh_ok(args, check=True, stdin=None):
        class R:
            stdout = "backend/a.php\nbackend/b.php"
            returncode = 0
        return R()

    class A:
        pr = 501
        json = False
        allow_self = False

    wire(gh_ok)
    out = tal.cmd_review_claim(A())

    check(out["pr"] == 501 and out["issue"] == 77, "trả về đúng PR + issue", str(out)[:120])
    check(out["files"] == ["backend/a.php", "backend/b.php"], "liệt kê file của PR", str(out.get("files")))
    check(refs_made == ["pr-501"], "có giành ref khoá review", str(refs_made))
    # Đây là assertion bắt lỗi gốc: dòng ledger nêu session, và trước bản vá nó
    # tham chiếu một biến CỤC BỘ CỦA HÀM KHÁC (`mine`) → NameError trước khi tới đây.
    check(notes and "revw9999" in notes[-1], "ghi ledger nêu session review", str(notes)[:160])
    check(refs_deleted == [] and unlocks == [], "đường thành công KHÔNG nhả khoá",
          f"deleted={refs_deleted} unlocks={unlocks}")

    # Lỗi SAU khi giành khoá — khoá phải được trả lại, không để lại vết không chủ.
    refs_made.clear()
    refs_deleted.clear()
    unlocks.clear()
    notes.clear()

    def gh_boom(args, check=True, stdin=None):
        raise RuntimeError("gh chết giữa chừng")

    wire(gh_boom)
    try:
        tal.cmd_review_claim(A())
        raised = False
    except RuntimeError:
        raised = True

    check(raised, "lỗi vẫn nổi lên, không bị nuốt")
    check(refs_deleted == ["pr-501"], "lỗi giữa chừng → XOÁ ref khoá", str(refs_deleted))
    check(unlocks == ["pr-501"], "lỗi giữa chừng → nhả cả khoá cục bộ", str(unlocks))

    restore_tal()

def test_released_lease_card():
    print("mark_lease_released + lease_file + do_assert")

    with tempfile.TemporaryDirectory() as d:
        wt = Path(d) / "issue-77"
        wt.mkdir()
        card = wt / tal.LEASE_FILE
        card.write_text(json.dumps({"issue": 77, "session": "s1", "epoch": 3, "keys": ["issue-77"]}))

        tal.mark_lease_released(wt)
        after = json.loads(card.read_text())

        check(card.is_file(), "thẻ vẫn còn trên đĩa (không bị xoá)")
        check(after.get("released") is True, "thẻ được đánh dấu released", str(after))
        check("epoch" not in after, "epoch bị bỏ — fencing token cũ không còn giá trị", str(after))
        check(bool(after.get("released_at")), "có mốc thời gian released_at")

        # lease_file đọc thẳng đường dẫn vẫn TRẢ VỀ thẻ — hook cần thấy nó.
        _, lf = tal.lease_file(wt, search=False)
        check(lf.get("released") is True, "lease_file(search=False) vẫn trả thẻ đã released")

        # do_assert phải từ chối rõ ràng, không được đi tiếp.
        tal.lease_file = lambda start=None, search=True: (wt, lf)
        try:
            tal.do_assert(quiet=True)
            check(False, "do_assert trên thẻ đã released phải Fail")
        except tal.Fail as e:
            check("LEASE ĐÃ NHẢ" in str(e), "do_assert báo đúng lý do", str(e)[:140])
            check("tal claim 77" in str(e), "thông điệp chỉ đúng lệnh cần chạy", str(e)[:140])

def test_hook_guard_not_a_trap():
    print("cmd_hook_guard: chặn GHI, không chặn chỗ đứng (#1382)")

    import contextlib
    import io

    MINE = "d4318e2a-mine"
    OTHER = "ffffffff-other"

    with tempfile.TemporaryDirectory() as td:
        wt = Path(td) / "issue-99"
        wt.mkdir()

        def card(**extra):
            (wt / tal.LEASE_FILE).write_text(json.dumps({
                "repo": "o/r", "issue": 99, "group": [99], "branch": "issue-99",
                "session": MINE, "keys": ["issue-99"], **extra,
            }))

        def guard(tool, ti, sid, cwd=str(wt)) -> bool:
            """True = BỊ CHẶN."""
            payload = json.dumps({"tool_name": tool, "tool_input": ti,
                                  "session_id": sid, "cwd": cwd})
            out, old = io.StringIO(), sys.stdin
            sys.stdin = io.StringIO(payload)
            try:
                with contextlib.redirect_stdout(out):
                    try:
                        tal.cmd_hook_guard(None)
                    except SystemExit:
                        pass
            finally:
                sys.stdin = old
            return "deny" in out.getvalue()

        def bash(cmd, sid=MINE):
            return guard("Bash", {"command": cmd}, sid)

        card(released=True, released_at="2026-07-30T23:24:45Z")

        # KHÔNG được nhốt: đọc và đi ra ngoài phải chạy được.
        check(not bash("pwd"), "`pwd` trong worktree đã nhả lease → CHO QUA")
        check(not bash("cd /tmp && ls"), "`cd` ra ngoài → CHO QUA (không nhốt)")
        for cmd in ("git status --porcelain", "git log --oneline -5", "git diff",
                    "git show HEAD", "git fetch origin dev", "git rev-parse HEAD",
                    "git merge-base HEAD dev", "git ls-files", "git ls-remote origin",
                    "git describe", "git blame file", "git cat-file -t HEAD",
                    "git for-each-ref", "git remote -v", "git branch --list",
                    "git worktree list", "git stash list", "git config --get user.name"):
            check(not bash(cmd), f"lệnh git chỉ đọc → CHO QUA: {cmd}")
        check(not bash("git -C /tmp status"), "git -C ngoài worktree, chỉ đọc → CHO QUA")
        check(not bash("git -C /tmp commit -m x"), "git -C ngoài worktree, ghi ngoài → CHO QUA")
        check(not bash("echo hi > /tmp/tal-hook-out.txt"), "redirect ra /tmp → CHO QUA")
        check(not bash("rm -rf /tmp/tal-hook-junk"), "rm đích /tmp → CHO QUA")
        check(not bash("sed -i s/a/b/ /tmp/tal-hook-file"), "sed -i đích /tmp → CHO QUA")
        check(not bash("sed -n '1p' file 2>/dev/null"), "sed đọc + 2>/dev/null → CHO QUA")
        # Lối thoát mà chính thông điệp deny quảng cáo phải thật sự đi được.
        check(not bash("tal claim 99"), "`tal claim` → CHO QUA (đúng lối thoát nó mách)")
        check(not bash(".claude/tools/agent-loop/tal status"), "`tal status` → CHO QUA")

        # Nới rào không được biến thành bỏ rào.
        check(bash("git commit -m x"), "`git commit` → CHẶN (worktree đã nhả lease)")
        check(bash("echo hong > f"), "chuyển hướng `>` → CHẶN")
        check(bash("rm -rf src"), "`rm -rf` → CHẶN")
        check(bash("sed -i s/a/b/ f.php"), "`sed -i` trong worktree → CHẶN")
        check(bash(f'''python3 -c 'open("{wt / "pwned.txt"}","w").write("x")' ''',
                   sid=OTHER), "Python ghi literal vào worktree session khác → CHẶN")
        check(guard("Bash", {"command": f'''node -e 'require("fs").writeFileSync("{wt / "n.txt"}","x")' '''},
                    OTHER, cwd="/tmp"),
              "Node đứng ngoài nhưng ghi literal vào worktree session khác → CHẶN")
        check(guard("Bash", {"command": f'''ruby -e 'File.write("{wt / "r.txt"}","x")' '''},
                    OTHER, cwd="/tmp"),
              "Ruby đứng ngoài nhưng ghi literal vào worktree session khác → CHẶN")
        check(guard("Edit", {"file_path": str(wt / "a.txt")}, MINE, cwd="/tmp"),
              "Edit vào worktree đã nhả lease → CHẶN (công cụ ghi vẫn xét đường dẫn)")

        # Session khác: cùng luật — đọc thì cho, ghi thì chặn.
        card(epoch=1)
        check(not bash("pwd", sid=OTHER), "session khác `pwd` → CHO QUA")
        check(bash("git commit -m x", sid=OTHER), "session khác `git commit` → CHẶN")

        # Rào theo MẪU LỆNH giữ nguyên: xét mọi lệnh Bash, kể cả của chủ lease.
        check(bash("git checkout -b hotfix-abc"), "tên branch sai → CHẶN (rào mẫu lệnh không đổi)")
        check(not bash("git checkout -b issue-99"), "tên `issue-99` → CHO QUA")

def test_dead_letter_counts_failures():
    print("dead-letter đếm vòng review CHƯA ĐẠT, không đếm lần claim (#1342)")

    src = TAL_SRC.read_text()
    i = src.index("failures = led.get(\"review_rounds\", 0)")
    blk = src[i:i + 400]

    check("failures >= MAX_ATTEMPTS" in blk,
          "ngưỡng đứng trên `failures`, không phải `attempts`", blk[:120])
    check('led["attempts"] > MAX_ATTEMPTS' not in src,
          "không còn chỗ nào lấy `attempts` làm ngưỡng dead-letter")
    check('led.get("review_rounds", 0)' in blk,
          "`failures` lấy từ review_rounds — chỉ tăng khi verdict `changes`")

    # Ngưỡng phải là >=, không phải >: MAX_ATTEMPTS=3 nghĩa là ĐÚNG 3 vòng hỏng
    # thì dừng, chứ không phải 4. Sai một đơn vị ở đây là một vòng review thừa.
    check(">= MAX_ATTEMPTS" in blk and "> MAX_ATTEMPTS" not in blk.replace(">= MAX_ATTEMPTS", ""),
          "dùng `>=` — MAX_ATTEMPTS=3 là dừng ở vòng hỏng thứ 3, không phải thứ 4")

def test_remove_worktree_rmtrees():
    print("remove_worktree xoá THẬT thư mục, không chỉ bỏ đăng ký (#1349)")

    src = TAL_SRC.read_text()
    blk = src[src.index("def remove_worktree("):]
    blk = blk[:blk.index("\ndef ", 10)]

    check("remove_orphan_tree(orphan)" in blk,
          "có xoá đã kiểm chứng — `remove --force` từ chối thì `prune` KHÔNG xoá thư mục "
          "(#2177: rmtree nhắm vào bản ĐÃ DỜI, không đục thẳng chỗ cũ)")
    check(blk.index("worktree\", \"remove\"") < blk.index("remove_orphan_tree")
          < blk.index("\"prune\""),
          "đúng thứ tự: remove → rmtree → prune")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        wtdir = root / ".claude" / "worktrees"
        (wtdir / "issue-5" / "vendor").mkdir(parents=True)
        (wtdir / "issue-5" / "vendor" / "big.bin").write_text("x")

        class FakeCtx:
            main_worktree = root
            worktrees_dir = wtdir
        tal.C = FakeCtx()
        tal.run = lambda *a, **k: None          # git remove/prune "thành công" mà không làm gì
        tal.branch_exists_local = lambda br: False

        tal.remove_worktree(5)
        check(not (wtdir / "issue-5").exists(),
              "thư mục biến mất kể cả khi git remove im lặng không làm gì")

def test_remove_worktree_failure_keeps_registration():
    """#2177 (a) — xoá thư mục THẤT BẠI thì KHÔNG prune.

    Trạng thái nguy hiểm nhất là nửa-chết: thư mục còn, đăng ký git mất. `cd`
    vào đó vẫn được, và mọi lệnh git từ đó im lặng giải về repo cha — 4 sự cố
    ghi nhầm cây chính trong một phiên. Nên khi không dời/xoá được thư mục,
    `remove_worktree` phải giữ nguyên đăng ký (không prune) và khai thật (False).
    """
    print("remove_worktree: không xoá được ⇒ KHÔNG prune, không nửa-chết (#2177)")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        wtdir = root / ".claude" / "worktrees"
        target = wtdir / "issue-7"
        (target / "vendor").mkdir(parents=True)
        (target / ".git").write_text("gitdir: /dau/do/.git/worktrees/issue-7\n")

        class FakeCtx:
            main_worktree = root
            worktrees_dir = wtdir
        tal.C = FakeCtx()

        calls: list[list[str]] = []

        def fake_run(cmd, cwd=None, check=True, stdin=None):
            calls.append(cmd)

            class R:
                returncode = 0
                stdout = ""
            return R()

        tal.run = fake_run                      # `git worktree remove` "chạy" mà không xoá gì
        tal.branch_exists_local = lambda br: False

        # (1) rename thất bại ⇒ phải giữ nguyên tất cả
        #
        # #3780 — TIÊM LỖI Ở CHÍNH `Path.rename`, KHÔNG bằng `chmod 0o555`.
        # Bản trước khoá quyền ghi thư mục cha rồi tin rằng rename sẽ hỏng. Điều
        # đó chỉ đúng khi uid != 0: **root bỏ qua bit quyền**, nên trong container
        # `swarm-pool` (chạy bằng root) rename THÀNH CÔNG, `ok` là True, và bài
        # đỏ vì MÔI TRƯỜNG chứ không vì hành vi sai. Đó là lý do duy nhất
        # `agent-loop-gate` không dời sang pool đó được.
        #
        # Tiêm thẳng vào `Path.rename` đo đúng thứ cần đo — "rename hỏng thì
        # `remove_worktree` xử ra sao" — và cho cùng một câu trả lời ở mọi uid.
        real_rename = Path.rename

        def rename_boom(self, target):
            raise OSError(13, "Permission denied (lỗi TIÊM bởi test #3780)")

        Path.rename = rename_boom
        try:
            ok = tal.remove_worktree(7)
        finally:
            Path.rename = real_rename
        check(ok is False, "trả False — không khai 'đã dọn' cho việc chưa làm")
        check(not any("prune" in c for c in calls),
              "KHÔNG chạy `git worktree prune` khi thư mục chưa dời/xoá được")
        check(target.exists() and (target / ".git").exists(),
              "thư mục + .git còn nguyên vẹn — git vẫn nhận worktree, không nửa-chết")

        # (2) hết khoá ⇒ dời được ⇒ đường dẫn cũ biến mất TRƯỚC khi prune chạy
        calls.clear()
        ok = tal.remove_worktree(7)
        check(ok is True, "dời được thì trả True")
        check(not target.exists(), "đường dẫn cũ hết tồn tại — prune từ đây là an toàn")
        check(any("prune" in c for c in calls), "prune CÓ chạy sau khi đã dời xong")

def test_merge_leaves_submodule_worktree_stale():
    """#1400 — vì sao `merge-batch` phải init submodule LẦN THỨ HAI, sau khi trộn.

    Đây là test trên fixture git THẬT, không mock: điều cần chứng minh là hành vi
    của chính `git`, nên mock nó đi thì test chỉ còn kiểm lại giả định của mình.

        sub:   c1 ── c2 ── c3
        super: base@c1 ;  prA→c3 ;  prB→c2

    Trộn prA rồi prB: git tự giải gitlink ("Note: Fast-forwarding submodule"), index
    thành c3 — nhưng cây con vẫn nằm ở c2, nên file đọc ra nội dung CŨ.
    """
    print("merge để cây con lệch pointer; `submodule update` kéo về (#1400)")

    import shutil
    import subprocess

    if not shutil.which("git"):
        check(False, "cần git để chạy test này", "không tìm thấy git trong PATH")
        return

    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "a@b.c",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "a@b.c",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}

    def git(*args, cwd):
        return subprocess.run(["git", "-c", "protocol.file.allow=always", *args],
                              cwd=str(cwd), env=env, capture_output=True, text=True)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sub, super_ = root / "sub", root / "super"

        sub.mkdir()
        git("init", "-q", "-b", "main", ".", cwd=sub)
        shas = []
        for i in ("1", "2", "3"):
            (sub / "f").write_text(i)
            git("add", "f", cwd=sub); git("commit", "-qm", f"c{i}", cwd=sub)
            shas.append(git("rev-parse", "HEAD", cwd=sub).stdout.strip())
        c1, c2, c3 = shas

        super_.mkdir()
        git("init", "-q", "-b", "main", ".", cwd=super_)
        git("submodule", "add", "-q", str(sub), "sub", cwd=super_)
        git("-C", "sub", "checkout", "-q", c1, cwd=super_)
        git("add", ".gitmodules", "sub", cwd=super_); git("commit", "-qm", "base", cwd=super_)

        for br, sha in (("prA", c3), ("prB", c2)):
            git("checkout", "-q", "main", cwd=super_)
            git("checkout", "-q", "-b", br, cwd=super_)
            git("-C", "sub", "checkout", "-q", sha, cwd=super_)
            git("add", "sub", cwd=super_); git("commit", "-qm", br, cwd=super_)

        git("checkout", "-q", "main", cwd=super_)
        for br in ("prA", "prB"):
            m = git("merge", "--no-edit", br, cwd=super_)
            check(m.returncode == 0, f"trộn {br} không conflict",
                  (m.stdout + m.stderr).strip()[:200])

        def index_ptr():
            return git("ls-files", "-s", "sub", cwd=super_).stdout.split()[1]

        def worktree_ptr():
            return git("-C", "sub", "rev-parse", "HEAD", cwd=super_).stdout.strip()

        # Đây là lỗi. Nếu một ngày git tự đồng bộ cây con thì hai dòng này đỏ — và
        # đó là tin tốt: lúc ấy bước init thứ hai trong merge-batch mới là thừa.
        check(index_ptr() == c3, "index mang pointer của lô (c3)", index_ptr()[:12])
        check(worktree_ptr() == c2,
              "cây con VẪN ở pointer cũ (c2) — merge không move nó",
              f"worktree={worktree_ptr()[:12]}")
        check((super_ / "sub" / "f").read_text() == "2",
              "file trong submodule đọc ra nội dung CŨ ⇒ full suite sẽ test nhầm code")

        # Và đây là bản sửa: đúng một lệnh, chính là lệnh merge-batch chạy lần hai.
        u = git("submodule", "update", "--init", cwd=super_)
        check(u.returncode == 0, "`git submodule update --init` chạy được",
              (u.stdout + u.stderr).strip()[:200])
        check(worktree_ptr() == c3, "sau khi đồng bộ: cây con khớp index",
              f"worktree={worktree_ptr()[:12]} index={index_ptr()[:12]}")
        check((super_ / "sub" / "f").read_text() == "3",
              "file đọc ra ĐÚNG nội dung của lô sắp merge")
        check(git("status", "--porcelain", cwd=super_).stdout.strip() == "",
              "cây sạch — không để lại ' M sub' cho bước sau hiểu nhầm")

def test_gc_spares_branch_with_open_pr():
    """#1413 — một branch được DÙNG LẠI qua nhiều vòng PR.

    Vòng 1 merge → vòng sửa mở PR mới từ cùng `issue-<N>` → `gc` thấy PR-đã-merge
    mang head đó và xoá branch, GitHub đóng luôn PR mới. Đã mất trắng hai PR đã
    test xong theo đúng đường này (closed 01:58:50, head_ref_deleted 01:58:51).

    Rào của #1385 không với tới: nó chừa issue có LEASE SỐNG, mà `tal pr` nhả
    lease ngay sau khi mở PR — đúng thiết kế. Khoảng mở-PR→merge là lúc branch
    cần được bảo vệ nhất và lại đang trần.
    """
    print("gc: chừa branch đang có PR MỞ (#1413)")

    deleted: list[str] = []

    def fake_gh_json(args, default=None):
        if "pr" in args and "--state" in args and "merged" in args:
            return [
                {"number": 1402, "headRefName": "issue-1392",
                 "headRepositoryOwner": {"login": "o"}},
                {"number": 1300, "headRefName": "issue-1299",
                 "headRepositoryOwner": {"login": "o"}},
            ]
        if "pr" in args and "--state" in args and "open" in args:
            # Vòng sửa: PR MỚI mở từ chính branch mà PR 1402 đã merge.
            return [{"headRefName": "issue-1392"}]
        return [{"ref": "refs/heads/issue-1392"}, {"ref": "refs/heads/issue-1299"}]

    tal.gh_json = fake_gh_json
    tal.gh = lambda args, check=True: deleted.append(args[-1]) or type("P", (), {})()

    acts = tal.delete_merged_branches("o/r", dry=False, protect={"main", "dev", "master"})
    killed = [a["branch"] for a in acts if "xoá" in a["action"]]
    spared = [a["branch"] for a in acts if "BỎ QUA" in a["action"]]

    check("issue-1392" not in killed,
          "KHÔNG xoá branch đang có PR mở, dù PR cũ cùng branch đã merge",
          "đây là đường đã mất trắng hai PR")
    check("issue-1392" in spared, "và nói rõ vì sao bỏ qua", str(acts))
    check("issue-1299" in killed,
          "vẫn dọn branch của PR đã merge mà KHÔNG còn PR mở — rào không được nới",
          str(killed))
    check(not any("issue-1392" in d for d in deleted),
          "không có lời gọi DELETE nào chạm branch được chừa", str(deleted))

def test_merge_and_gc_close_through_the_same_gate():
    """`Closes #N` không bao giờ chạy ở quy trình này.

    GitHub chỉ tự đóng khi PR merge vào DEFAULT BRANCH, mà default của repo là
    `main` còn mọi PR ở đây nhắm `dev`. Trước #1462 cũng không có `gh issue
    close` ở đâu — issue nằm OPEN + status:shipped vô thời hạn (22 cái, dọn tay
    ngày 2026-08-01).
    """
    print("cmd_merge + gc: cùng đi qua closable(), gc đóng theo mặc định (#1462)")
    src = TAL_SRC.read_text()

    blk = src[src.index("def cmd_merge("):]
    blk = blk[:blk.index("\ndef ", 10)]
    check('"issue", "close"' in blk, "cmd_merge gọi `gh issue close`")
    check("closable(" in blk, "cmd_merge đi qua rào closable, không đóng thẳng tay")
    check(blk.index("set_state_labels") < blk.index('"issue", "close"'),
          "đóng SAU khi gắn nhãn — nhãn phải còn trên issue đã đóng để tra cứu")

    gc = src[src.index("def cmd_gc("):]
    gc = gc[:gc.index("\ndef ", 10)]
    check("no_close" in gc and "closable(" in gc,
          "gc đóng theo mặc định và dùng CHUNG rào với cmd_merge",
          "hai đường đóng khác luật là hai lần cơ hội lệch nhau")

def test_realign_checks_submodule_is_checked_out():
    """#1462 — git trong thư mục submodule RỖNG leo lên repo cha.

    Khi đó `origin/dev` là tip của UMBRELLA, nên phép so tổ tiên đem pointer của
    submodule so với SHA của repo khác: luôn "phân kỳ", luôn chặn merge. Đã chặn
    thật PR #1415 với `pos-web (061da1cbf) KHÔNG phải tổ tiên của tip 42aa84a04`
    — trong đó 42aa84a04 là commit UMBRELLA, không tồn tại trong pos-web.
    """
    print("realign_pointers: bắt buộc submodule đã checkout trước khi so (#1462)")
    src = TAL_SRC.read_text()
    blk = src[src.index("def realign_pointers("):]
    blk = blk[:blk.index("\ndef ", 10)]
    check("--show-toplevel" in blk,
          "kiểm toplevel của repo con khớp đúng thư mục đó",
          "không kiểm thì git lặng lẽ trả lời bằng repo cha")
    check(blk.index("--show-toplevel") < blk.index("merge-base"),
          "kiểm TRƯỚC khi so tổ tiên, không phải sau")
    check('"submodule", "update", "--init"' in blk,
          "tự init submodule chưa checkout thay vì chỉ báo lỗi")

def test_audit_blocks_child_pr_on_wrong_base():
    """PR con nhắm base ≠ `dev` phải CHẶN.

    `customer-web#96` nhắm `info-customer`: PR merge, `tal gc` xoá nhánh
    `issue-N`, và commit mà umbrella đang trỏ tới chỉ còn sống nhờ một nhánh
    feature. Nhánh đó biến mất là mọi clone mới chết ở `submodule update`.
    """
    print("submodule_audit: PR con nhắm sai base thì CHẶN (#1465)")
    src = TAL_SRC.read_text()
    blk = src[src.index("def submodule_audit("):]
    blk = blk[:blk.index("\ndef ", 10)]
    check("baseRefName" in blk, "audit đọc base của PR con")
    check("wrong-base" in blk, "có mã lỗi riêng cho base sai, không lẫn vào no-pr")
    # #2300 F6 — chuẩn so là branch .gitmodules khai (chính là base submodule-pr
    # DÙNG để tạo PR); so cứng BASE_BRANCH của umbrella là tal tự tạo PR ở base X
    # rồi tự chặn chính PR đó khi submodule track branch khác dev.
    check("b != want_base" in blk and 's.get("branch")' in blk,
          "so với branch của .gitmodules (want_base), không hard-code tên nhánh",
          "so cứng BASE_BRANCH umbrella thì submodule track nhánh khác là tự chặn PR mình tạo")

def test_doctor_scans_for_dangling_pointers():
    """`tal doctor` phải quét được đúng lỗi #1465 bằng MỘT lệnh.

    Phép kiểm đúng KHÔNG phải "commit có trên origin/issue-N" — nhánh đó rồi sẽ
    bị xoá — mà là "sau khi mọi nhánh tạm biến mất, commit còn với tới được từ
    `dev` của repo con không".
    """
    print("doctor: quét con trỏ chỉ sống nhờ nhánh feature (#1465)")
    src = TAL_SRC.read_text()
    check("def dangling_pointers(" in src, "có hàm quét riêng, gọi lại được")
    blk = src[src.index("def dangling_pointers("):]
    blk = blk[:blk.index("\ndef ", 10)]
    check('f"origin/{BASE_BRANCH}"' in blk,
          "đối chiếu với origin/dev của REPO CON",
          "đối chiếu với issue-N là kiểm nhầm thứ sắp bị xoá")
    check("cat-file" in blk and "merge-base" in blk,
          "kiểm cả hai ca: commit không tồn tại, và tồn tại nhưng ngoài dev")
    check("--contains" in blk, "nói rõ nó đang sống nhờ nhánh nào")

    doc = src[src.index("def cmd_doctor("):]
    doc = doc[:doc.index("\ndef ", 10)]
    check("dangling_pointers()" in doc, "doctor thật sự gọi nó")

def test_claim_rollback_spares_adopted_refs():
    """Rollback chỉ được trả lại ref MÌNH VỪA TẠO.

    Xoá cả ref chỉ nhận lại là tự tay vứt một lease đang giữ — biến một lần
    claim hỏng thành mất quyền ghi trên việc đang làm dở.
    """
    print("claim: rollback chừa ref chỉ nhận lại, không xoá bừa (#1476)")
    src = TAL_SRC.read_text()
    blk = src[src.index("def cmd_claim("):]
    blk = blk[:blk.index("\ndef ", 10)]

    check("adopted" in blk and "created" in blk,
          "tách hai danh sách: ref vừa tạo vs ref nhận lại")
    roll = blk[blk.index("except Fail:"):]
    check("for k in created:" in roll, "rollback chỉ duyệt `created`")
    check("for k in adopted:" not in roll, "rollback KHÔNG đụng `adopted`")
    check("lease_is_mine(" in blk, "claim hỏi sổ khi ref đã tồn tại")

def test_merge_gates_on_dangling_pointer():
    """Umbrella không được merge khi con trỏ chưa nằm trên `dev` repo con.

    Ba lớp trước đều hụt: `submodule_audit` chỉ chạy lúc `tal pr`;
    `dangling_pointers()` chỉ nằm trong `doctor` (phải tự nhớ chạy);
    `realign_pointers()` chỉ căn khi con trỏ là TỔ TIÊN của tip — con trỏ chết
    thì không phải tổ tiên của gì cả nên nó im lặng bỏ qua.

    Lọt BA LẦN trong ngày 2026-08-01, cả ba là `customer-web` trỏ vào commit chỉ
    sống trên nhánh feature ⇒ clone mới chết ở `submodule update`.
    """
    print("cmd_merge: chặn con trỏ chưa vào dev repo con (#1487)")
    src = TAL_SRC.read_text()

    check("def pr_dangling_pointers(" in src, "có hàm kiểm riêng, gọi lại được")

    fn = src[src.index("def pr_dangling_pointers("):]
    fn = fn[:fn.index("\ndef ", 10)]
    check("headRefName" in fn, "đọc con trỏ từ HEAD của PR, không phải từ dev")
    check('f"origin/{BASE_BRANCH}"' in fn, "đối chiếu với origin/dev của REPO CON")
    check("cat-file" in fn and "merge-base" in fn,
          "bắt cả hai ca: commit không tồn tại, và tồn tại nhưng ngoài dev")
    check("--contains" in fn, "nói rõ con trỏ đang sống nhờ nhánh nào")

    blk = src[src.index("def cmd_merge("):]
    blk = blk[:blk.index("\ndef ", 10)]
    check("pr_dangling_pointers(pr)" in blk, "cmd_merge thật sự gọi cổng")
    # Thứ tự quan trọng: phải SAU merge_sub_prs/realign (con trỏ còn có thể được
    # sửa), và TRƯỚC `gh pr merge` (sau đó thì đã muộn).
    check(blk.index("merge_sub_prs(") < blk.index("pr_dangling_pointers(pr)"),
          "chạy SAU khi cụm repo con đã merge + căn lại",
          "chạy trước thì chặn oan đúng những PR mà realign sắp sửa xong")
    check(blk.index("pr_dangling_pointers(pr)") < blk.index('"pr", "merge"'),
          "chạy TRƯỚC khi merge thật")
    check("a.force" in blk.split("pr_dangling_pointers(pr)")[1][:400],
          "`--force` mở được, nhưng phải tường minh")

def test_pr_merge_never_sets_review_label():
    """`pr-merge` KHÔNG được tự gắn `agent:review-passed`.

    Nhãn đó là bằng chứng đã có người đọc lại. Lệnh tự gắn thì nó chỉ còn là một
    bước thủ tục, và cổng tách vai — lý do tồn tại của cả vòng lặp — chết theo.
    """
    print("pr-merge: dừng khi thiếu review, KHÔNG tự gắn nhãn (#1524)")
    src = TAL_SRC.read_text()
    blk = src[src.index("def cmd_pr_merge("):]
    blk = blk[:blk.index("\ndef ", 10)]

    check("set_state_labels" not in blk and "add-label" not in blk,
          "không có chỗ nào gắn nhãn",
          "tự gắn là vô hiệu hoá cổng tách vai")
    check("merge_blockers(" in blk, "dùng chung cổng với `tal merge`")
    check("L_PASSED" in blk, "thông điệp nêu đúng tên nhãn còn thiếu")
    check("cmd_merge(a)" in blk,
          "kết thúc bằng cmd_merge — không chép lại logic merge",
          "chép lại là hai đường merge khác luật, đúng thứ #1462 đã phải sửa")

    # Thứ tự chặng: chờ CI của CON phải đứng trước chờ CI của UMBRELLA. So bằng
    # đúng hai lời gọi, không so bằng chữ trong docstring.
    check(blk.index('wait_checks(sp[') < blk.index("wait_checks(C.repo"),
          "chờ CI PR con trước, umbrella sau",
          "đảo lại là chờ umbrella xanh rồi mới biết con đỏ — mất cả lượt chờ")

def test_gc_spares_reopened_issue():
    """`gc` đóng lại một issue vừa được MỞ LẠI có chủ ý (#1571).

    Đo được thật, bốn lần trong một phiên: một PR làm xong MỘT PHẦN issue,
    `Closes #N` đóng nó, tôi mở lại kèm comment liệt kê phần còn lại — rồi `gc`
    ĐÓNG LẠI trong vòng 5 phút. #962 · #1564 · #1568 · #1574 đều dính.

    Hai lỗi chồng nhau, và bài test này ghim cả hai:

      1. `gc` gắn `status:shipped` VÔ ĐIỀU KIỆN rồi mới hỏi `closable()` để quyết
         định có đóng không — nên nó in "KHÔNG đóng #962: còn mang status:planning"
         NGAY SAU KHI vừa gắn `status:shipped` cho chính #962. Issue mang cả hai
         nhãn, `tal queue` lọc theo nhãn ⇒ rơi khỏi hàng đợi.

      2. `closable()` không phân biệt "chưa từng đóng" với "đã đóng rồi mở lại".
         Nhãn `status:*` không cứu được: issue mở lại thường mang `agent:ready`.
    """
    print("gc: issue MỞ LẠI sau khi PR merge thì không được đụng vào (#1571)")

    src = TAL_SRC.read_text()

    check("def reopened_after(" in src,
          "có hàm reopened_after()",
          "không có tín hiệu nào khác phân biệt được reopen cố ý với chưa-từng-đóng")

    blk = src[src.index("def closable("):]
    blk = blk[:blk.index("\ndef ", 10)]
    check("reopened_after(" in blk, "closable() hỏi reopened_after()")
    check("merged_at" in blk, "closable() nhận mốc thời gian merge")

    # Fail-safe: đọc timeline hỏng thì phải nghiêng về KHÔNG đụng vào issue.
    rblk = src[src.index("def reopened_after("):]
    rblk = rblk[:rblk.index("\ndef ", 10)]
    check("return True" in rblk.split("is None")[1][:120] if "is None" in rblk else False,
          "timeline không đọc được ⇒ coi như đã mở lại (fail-safe)",
          "đóng nhầm là mất việc; bỏ qua nhầm chỉ là một dòng nhãn cũ")

    # Lỗi gốc: gắn nhãn phải chịu CÙNG điều kiện với đóng.
    gblk = src[src.index("def cmd_gc("):]
    gblk = gblk[:gblk.index("\ndef ", 10)]
    i_verdict = gblk.find("closable(")
    i_label = gblk.find("set_state_labels(")
    check(i_verdict != -1 and i_label != -1 and i_verdict < i_label,
          "gc hỏi closable() TRƯỚC khi gắn nhãn",
          "gắn trước hỏi sau chính là lỗi: nhãn dính lại dù từ chối đóng")
    check("mergedAt" in gblk, "gc lấy mergedAt từ danh sách PR")
    check("KHÔNG đụng #" in gblk,
          "gc nói rõ nó BỎ QUA issue nào",
          "im lặng bỏ qua thì lần sau lại phải điều tra từ đầu")

def test_queue_refuses_to_call_it_empty_when_it_could_not_measure():
    print("cmd_queue (gh hỏng ⇒ RAISE, không in 'hàng đợi rỗng')")

    # Đúng hình dạng đã tái hiện được: hạn mức GraphQL cạn, `gh` thoát 1, và
    # `gh_json(default=[])` biến nó thành danh sách rỗng ⇒ tal in câu trấn an
    # kèm exit 0 trong khi ba issue `agent:ready` vẫn mở.
    def gh_rate_limited(args, check=True, stdin=None):
        class R:
            stdout = ""
            stderr = "GraphQL: API rate limit already exceeded for user ID 26842626."
            returncode = 1
        return R()

    tal.gh = gh_rate_limited
    tal.refs_all = lambda: []

    class A:
        json = False
        verbose = False
        limit = 10

    try:
        tal.cmd_queue(A())
    except tal.Fail as e:
        msg = str(e)
        check("KHÔNG ĐO ĐƯỢC" in msg, "nêu rõ KHÔNG ĐO ĐƯỢC", msg)
        check("rate limit" in msg, "mang theo lỗi thật của gh", msg)
        check("rate_limit" in msg, "gợi ý chỗ kiểm quota", msg)
    else:
        check(False, "phải RAISE thay vì báo hàng đợi rỗng")

def test_queue_still_reports_a_genuinely_empty_backlog():
    print("cmd_queue (gh trả [] thật ⇒ vẫn là 'hàng đợi rỗng')")

    # Mặt kia của bánh cóc: bản sửa KHÔNG được biến một backlog rỗng thật thành
    # lỗi — nếu không thì vòng lặp kêu ầm mỗi khi thực sự hết việc.
    def gh_empty(args, check=True, stdin=None):
        class R:
            stdout = "[]"
            stderr = ""
            returncode = 0
        return R()

    tal.gh = gh_empty
    tal.refs_all = lambda: []

    class A:
        json = True
        verbose = False
        limit = 10

    out = tal.cmd_queue(A())
    check(out["eligible"] == [], "đo được và trả về rỗng, không ném")

def test_adopt_restores_the_card_without_bumping_epoch():
    """#2238 — thẻ mất trong khi lease vẫn sống phải có đường về KHÔNG phá gì."""
    print("cmd_adopt: dựng lại thẻ từ sổ, epoch GIỮ NGUYÊN (#2238)")

    with tempfile.TemporaryDirectory() as td:
        me = tal.session_id()
        wt, led, writes = _adopt_world(td, owner=me, epoch=7)
        card = wt / tal.LEASE_FILE

        # Trạng thái sự cố: lease sống trên ref + sổ, nhưng thẻ đã mất.
        check(not card.exists(), "xuất phát: không có thẻ trên đĩa")
        try:
            tal.lease_file(wt, search=False)
            check(False, "lease_file phải Fail khi mất thẻ")
        except tal.Fail as e:
            check(e.code == 3, "lease_file vẫn Fail(…, 3) như cũ", str(e.code))
            check("tal adopt" in str(e), "thông điệp CHỈ ra đường phục hồi, không đẩy về claim", str(e))

        out = tal.cmd_adopt(_AdoptArgs())          # không truyền issue → phải tự suy ra

        check(out["issue"] == 2238, "suy đúng issue từ sổ khi không đứng trong worktree", str(out))
        check(card.is_file(), "thẻ đã được dựng lại")
        got = json.loads(card.read_text())
        check(got["epoch"] == 7, "epoch GIỮ NGUYÊN — không bump", str(got.get("epoch")))
        check(led["epoch"] == 7, "sổ cũng không bị bump", str(led["epoch"]))
        check(got["session"] == me, "thẻ ghi đúng session đang chạy")
        check(got["comment_id"] == 5226320939, "thẻ mang comment_id của sổ", str(got))
        check(writes == [], "KHÔNG ghi gì lên sổ (ghi = lặng lẽ gia hạn lease)", str(writes))

        # Và cái quan trọng: sau adopt thì cổng ghi mở lại, đúng epoch cũ.
        tal.lease_file = lambda start=None, search=True: (wt, json.loads(card.read_text()))
        st = tal.do_assert(quiet=True)
        check(st["epoch"] == 7, "do_assert xanh với ĐÚNG epoch cũ", str(st))

def test_adopt_refuses_a_lease_that_belongs_to_another_session():
    """Bài quan trọng nhất: không có nó thì `adopt` chính là cửa sau."""
    print("cmd_adopt: TỪ CHỐI lease của session khác (#2238)")

    with tempfile.TemporaryDirectory() as td:
        wt, led, writes = _adopt_world(td, owner="SESSION-CUA-NGUOI-KHAC", epoch=4)
        card = wt / tal.LEASE_FILE

        try:
            tal.cmd_adopt(_AdoptArgs(issue=2238))
            check(False, "phải TỪ CHỐI, không được dựng thẻ")
        except tal.Fail as e:
            check(e.code == 5, "thoát bằng mã tách-vai (5), không phải 'không thấy thẻ' (3)", str(e.code))
            check("KHÔNG phải bạn" in str(e), "nói rõ lease là của người khác", str(e))
            check("cần người" in str(e), "chỉ ra đây là ca cần người, không tự xử", str(e))

        check(not card.exists(), "KHÔNG có thẻ nào được ghi ra")
        check(led["epoch"] == 4, "sổ không bị đụng vào", str(led["epoch"]))
        check(writes == [], "không ghi gì lên sổ", str(writes))

def test_adopt_refuses_when_the_lease_ref_is_already_gone():
    """Sổ nói của mình nhưng ref đã mất = lease đã bị thu hồi. Dựng thẻ là dựng ảo giác."""
    print("cmd_adopt: TỪ CHỐI khi ref CAS đã chết (#2238)")

    with tempfile.TemporaryDirectory() as td:
        wt, led, writes = _adopt_world(td, owner=tal.session_id(), epoch=2, ref_alive=False)
        card = wt / tal.LEASE_FILE

        try:
            tal.cmd_adopt(_AdoptArgs(issue=2238))
            check(False, "phải TỪ CHỐI khi ref không còn")
        except tal.Fail as e:
            check("ref issue-2238 KHÔNG còn" in str(e), "nêu đúng thứ đã mất", str(e))
            check("tal claim 2238" in str(e), "đẩy về claim — ca này epoch PHẢI tăng", str(e))

        check(not card.exists(), "KHÔNG có thẻ nào được ghi ra")
        check(writes == [], "không ghi gì lên sổ", str(writes))

def test_a_newly_added_test_actually_runs():
    """#2202 — rào cho chính cái rào: suite phải tự phát hiện test.

    Không kiểm bằng cách đọc `main()` (ghim văn bản thì đổi cách viết là hỏng),
    mà bằng cách LÀM đúng việc đã cắn ở #2156: thêm một ca `test_*` mới vào cuối
    danh sách rồi đòi suite nổ vì nó. Bản tuple-liệt-kê-tay cho ra XANH ở đây —
    đó chính là lỗi.
    """
    print("main(): ca test mới thêm được CHẠY, không cần đăng ký (#2202)")

    import ast
    import subprocess

    src = Path(__file__).read_text()

    # (a) khối `if __name__` phải là câu lệnh CUỐI CÙNG ở cấp module. Bẫy thứ hai
    #     của #2156: hàm định nghĩa SAU khối đó chưa tồn tại lúc `main()` chạy —
    #     `sys.exit` đã cắt ngang. Tự phát hiện không cứu được ca này, chỉ thứ tự
    #     trong file mới cứu, nên ghim thứ tự.
    tree = ast.parse(src)
    last = tree.body[-1]
    check(isinstance(last, ast.If) and "__main__" in ast.dump(last.test),
          "khối `if __name__` là câu lệnh CUỐI file — def sau nó sẽ không kịp tồn tại",
          type(last).__name__)

    # (b) discover_tests() thấy ĐÚNG tập `def test_*` cấp module trong file nguồn.
    in_source = {n.name for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}
    discovered = {fn.__name__ for fn in discover_tests()}
    check(discovered == in_source,
          f"phát hiện đủ {len(in_source)} ca có trong file nguồn",
          f"thiếu={sorted(in_source - discovered)} thừa={sorted(discovered - in_source)}")
    check(len(in_source) >= MIN_TESTS,
          f"số ca ({len(in_source)}) không tụt dưới ngưỡng MIN_TESTS={MIN_TESTS}")

    if os.environ.get("TAL_TEST_NO_SPAWN"):
        print("  ·    (bản con: bỏ qua bước sinh tiến trình để khỏi đệ quy)")
        return

    # (c) phép đo thật: chạy một BẢN SAO của chính file này, có nhét thêm một ca
    #     test hỏng ngay trước khối `if __name__` — đúng chỗ người ta thêm test.
    #     Suite con PHẢI đỏ và PHẢI gọi tên nó.
    marker = "CANARY_2202_DA_CHAY"
    canary = (f'def test_zzz_canary_2202():\n'
              f'    print("canary #2202")\n'
              f'    check(False, "{marker}")\n\n\n')
    # Lần xuất hiện CUỐI mới là khối thật — chuỗi này còn nằm trong chính ca test
    # đang đọc, nên `replace` sẽ nhét canary vào giữa một literal và làm hỏng file.
    anchor = 'if __name__ == "__main__":'
    head, tail = src.rsplit(anchor, 1)
    child_src = head + canary + anchor + tail
    # +1 chứ không phải ==1: tên canary đã xuất hiện sẵn trong file này (nó nằm
    # trong chính chuỗi đang dựng ở trên), nên phép đo là "nhiều hơn bản gốc một".
    check(child_src.count("def test_zzz_canary_2202")
          == src.count("def test_zzz_canary_2202") + 1,
          "chèn đúng MỘT ca canary, ngay trước khối `if __name__` cuối file")

    with tempfile.TemporaryDirectory() as td:
        child = Path(td) / "tal_test_child.py"
        child.write_text(child_src)
        os.symlink(HERE / "tal", Path(td) / "tal")   # load_tal() đọc `tal` cạnh file
        env = dict(os.environ, TAL_TEST_NO_SPAWN="1")
        p = subprocess.run([sys.executable, str(child)], capture_output=True, text=True, env=env)

    out = p.stdout + p.stderr
    # MỘT phép đo, hai điều kiện cùng lúc — cố ý. Tách ra thì "đỏ" một mình đậu
    # được vì lý do khác (suite con đỏ ở ca khác) và cho cảm giác đã canh.
    check(p.returncode == 1 and marker in out,
          "suite con ĐỎ và gọi ĐÚNG TÊN ca mới thêm — tức là ca đó đã thật sự chạy",
          f"returncode={p.returncode}; có marker={marker in out}; đuôi output: {out[-400:]}")

def test_verdict_refuses_a_merged_pr():
    """Race đo được ngoài đời: review claim 14:17:49Z, PR merge 14:18:38Z, verdict
    `changes` (blocking, ĐÚNG) ghi 14:20:11Z — muộn 93 giây. Hệ quả: issue #2110
    dính `agent:changes-requested` + `status:blocked` trên một PR đã đóng, kẹt
    vĩnh viễn, còn điểm blocking thật nằm nguyên trên dev không ai nợ."""
    print("cmd_review_verdict (#2153: PR đã merge ⇒ TỪ CHỐI ghi verdict)")

    calls: list[list[str]] = []
    written: list[str] = []
    labels: list = []
    refs_deleted: list[str] = []
    unlocks: list[str] = []

    def fake_gh(args, check=True, stdin=None):
        calls.append(args)

        class R:
            stdout = ""
            returncode = 0
        return R()

    tal.gh = fake_gh
    tal.pr_issue = lambda pr: 2110
    tal.ledger_read = lambda issue: ({"issue": 2110, "group": [2110], "state": "reviewing",
                                      "review_rounds": 0, "history": []}, 1, tal.now())
    tal.ledger_write = lambda led, cid, note=None: written.append(note)
    tal.set_state_labels = lambda *a, **k: labels.append(a)
    tal.ref_delete = lambda key: refs_deleted.append(key)
    tal.local_unlock = lambda key: unlocks.append(key)
    tal.session_id = lambda: "revw0000aaaa"
    tal.gh_json = lambda args, default=None: (
        {"state": "MERGED", "mergedAt": "2026-08-07T14:18:38Z", "headRefOid": "feedface"}
        if "state,mergedAt,headRefOid" in args else default)

    class A:
        pr = 2148
        verdict = "changes"
        body = "issue (blocking): con trỏ submodule tụt 1"
        body_file = None
        allow_self = False

    try:
        tal.cmd_review_verdict(A())
        failed = None
    except tal.Fail as e:
        failed = str(e)

    check(failed is not None, "PR MERGED → Fail, không exit 0")
    check(bool(failed) and "2153" in failed and "issue MỚI" in failed,
          "thông điệp nói rõ: verdict vô nghĩa, mở issue mới cho điểm blocking", str(failed)[:200])
    check(not any(c[:2] == ["pr", "comment"] for c in calls), "KHÔNG ghi comment verdict lên PR")
    check(written == [], "KHÔNG ghi sổ — giữ nguyên trạng thái mà merge đã ghi", str(written))
    check(labels == [], "KHÔNG dán nhãn changes-requested lên issue đã khép", str(labels))
    check(refs_deleted == ["pr-2148"] and unlocks == ["pr-2148"],
          "lease review được NHẢ, không treo `?` tới hết TTL", f"{refs_deleted} {unlocks}")

    # Không ĐO được state ⇒ cũng từ chối kết luận (#2151), nhưng GIỮ lease để thử lại.
    refs_deleted.clear()
    unlocks.clear()
    calls.clear()
    tal.gh_json = lambda args, default=None: default
    try:
        tal.cmd_review_verdict(A())
        failed = None
    except tal.Fail as e:
        failed = str(e)
    check(failed is not None and "KHÔNG ĐO ĐƯỢC" in str(failed),
          "state không đọc được → không kết luận (#2151)", str(failed)[:160])
    check(refs_deleted == [] and unlocks == [], "không đo được thì KHÔNG nhả lease",
          f"{refs_deleted} {unlocks}")

def test_ref_create_wraps_payload_in_a_tag_object():
    print("ref_create (#2172: payload → tag object; tạo tag hỏng thì rơi về sha trần)")

    gh_calls: list[list[str]] = []

    def fake_gh(args, check=True, stdin=None):
        gh_calls.append(args)

        class R:
            stdout = ""
            stderr = ""
            returncode = 0
        return R()

    tal.gh = fake_gh
    tal.gh_json = lambda args, default=None: (
        {"sha": "TAG0BEEF"} if any("git/tags" in str(x) for x in args) else default)

    ok = tal.ref_create("pr-9", "c0mm1t5ha", {"session": "s1"})
    ref_call = next(c for c in gh_calls if any("git/refs" in str(x) for x in c))
    check(ok is True and any("sha=TAG0BEEF" in str(x) for x in ref_call),
          "ref trỏ vào TAG object mang payload, không phải commit trần", str(ref_call))

    # Tạo tag hỏng → payload là phụ trợ, CAS vẫn phải chạy trên sha trần.
    gh_calls.clear()
    tal.gh_json = lambda args, default=None: default
    ok = tal.ref_create("pr-9", "c0mm1t5ha", {"session": "s1"})
    ref_call = next(c for c in gh_calls if any("git/refs" in str(x) for x in c))
    check(ok is True and any("sha=c0mm1t5ha" in str(x) for x in ref_call),
          "tag hỏng → rơi về sha trần, không chặn việc giành lease", str(ref_call))

    # Không payload → không đụng tới git/tags (đường cũ giữ nguyên giá).
    gh_calls.clear()
    tal.gh_json = lambda args, default=None: check_fail_if_called(args)

    def check_fail_if_called(args):
        raise AssertionError("không được gọi gh_json khi không có payload")

    ok = tal.ref_create("issue-7", "c0mm1t5ha")
    check(ok is True, "ref không payload vẫn tạo như cũ, không thêm round-trip")

def test_review_claim_stamps_owner_payload_on_the_ref():
    print("cmd_review_claim (#2172: ref mang danh tính chủ lease; #2153: PR đóng thì từ chối)")

    got: dict = {}
    tal.pr_issue = lambda pr: 55
    tal.ledger_read = lambda n: ({"issue": 55, "history": []}, 1, tal.now())
    tal.ledger_write = lambda led, cid, note=None: 1
    tal.local_lock = lambda k: True
    tal.local_unlock = lambda k: None
    tal.gh_json = lambda args, default=None: {"state": "OPEN"}
    tal.gh = lambda args, check=True, stdin=None: types.SimpleNamespace(stdout="", returncode=0)
    tal.head_sha = lambda: "beef"
    tal.session_id = lambda: "sess5555ffff"

    def cap(key, sha, payload=None):
        got["key"], got["payload"] = key, payload
        return True

    tal.ref_create = cap
    tal.cmd_review_claim(types.SimpleNamespace(pr=555, json=False, allow_self=False))
    p = got.get("payload") or {}
    check(got.get("key") == "pr-555" and p.get("session") == "sess5555ffff",
          "payload mang session THẬT của người claim", str(p)[:160])
    check(bool(p.get("expires_at")) and bool(p.get("host")) and bool(p.get("pid")),
          "payload đủ host/pid/hạn — status in được 'ai giữ, còn bao lâu'", str(p)[:200])

    # PR đã merge/đóng → chặn từ cửa vào (#2153), khỏi phí một lượt review.
    tal.gh_json = lambda args, default=None: {"state": "MERGED"}
    try:
        tal.cmd_review_claim(types.SimpleNamespace(pr=555, json=False, allow_self=False))
        refused = False
    except tal.Fail as e:
        refused = "2153" in str(e)
    check(refused, "PR đã MERGED → review-claim từ chối ngay (#2153)")

def test_unlock_pr_requires_note():
    """#2261 — mở khoá lease review phải có --note."""
    print("cmd_unlock: pr-* bắt buộc --note (#2261)")
    src = TAL_SRC.read_text()
    blk = src[src.index("def cmd_unlock("):]
    blk = blk[:blk.index("\ndef ", 10)]
    check('key.startswith("pr-")' in blk and "--note" in blk,
          "cmd_unlock kiểm pr-* và đòi note")
    check("MỞ KHOÁ LEASE REVIEW TAY" in blk, "ghi comment lên PR khi unlock pr-*")

    tal.ref_delete = lambda k: None
    tal.local_unlock = lambda k: None
    tal.gh = _gh_stub_with_head()
    tal.run = _run_stub_ancestor(True)      # #2988 — merge thật ⇒ head đã vào base

    class A:
        key = "pr-501"
        force = True
        note = ""

    try:
        tal.cmd_unlock(A())
        check(False, "unlock pr-* không note phải FAIL")
    except tal.Fail as e:
        check("2261" in str(e) or "note" in str(e).lower(), "nói rõ thiếu note", str(e))

def test_verdict_resets_issue_when_pr_closed_without_merge():
    """#2289 — CLOSED không merge ≠ MERGED: issue phải về hàng đợi code."""
    print("cmd_review_verdict (#2289: CLOSED không merge → trả issue về queue)")

    written: list[str] = []
    labels: list = []

    tal.pr_issue = lambda pr: 2289
    tal.ledger_read = lambda issue: ({"issue": 2289, "group": [2289], "state": "reviewing",
                                      "review_rounds": 0, "history": []}, 1, tal.now())
    tal.ledger_write = lambda led, cid, note=None: written.append(note)
    tal.set_state_labels = lambda issue, desired, drop=None: labels.append((issue, desired, drop))
    tal.ref_delete = lambda key: None
    tal.local_unlock = lambda key: None
    tal.session_id = lambda: "revw0000bbbb"
    tal.issue_data = lambda n: {"number": n, "state": "OPEN", "labels": []}
    tal.gh = lambda *a, **k: type("R", (), {"stdout": "", "stderr": "", "returncode": 0})()
    tal.gh_json = lambda args, default=None: (
        {"state": "CLOSED", "mergedAt": None, "headRefOid": "abc"}
        if "state,mergedAt,headRefOid" in args else default)

    class A:
        pr = 9001
        verdict = "pass"
        body = "ok"
        body_file = None
        allow_self = False

    try:
        tal.cmd_review_verdict(A())
        failed = None
    except tal.Fail as e:
        failed = str(e)

    check(failed is not None and "2289" in failed and "tal claim 2289" in failed,
          "nói rõ issue đã trả về hàng đợi", str(failed)[:200])
    check(any("đóng không merge" in w for w in written), "ghi sổ lý do", str(written))
    check(labels and tal.L_READY in labels[0][1] and tal.L_AWAIT in (labels[0][2] or set()),
          "gắn lại ready, gỡ awaiting-review", str(labels))

def test_verdict_skips_reset_when_issue_shipped():
    """#2289 — không gỡ shipped khi PR cũ closed-không-merge."""
    print("cmd_review_verdict (#2289: shipped issue → không reset)")

    written: list[str] = []
    labels: list = []

    tal.pr_issue = lambda pr: 2289
    tal.ledger_read = lambda issue: ({"issue": 2289, "group": [2289], "state": "shipped",
                                      "review_rounds": 0, "history": []}, 1, tal.now())
    tal.ledger_write = lambda led, cid, note=None: written.append(note)
    tal.set_state_labels = lambda issue, desired, drop=None: labels.append((issue, desired, drop))
    tal.issue_data = lambda n: {"number": n, "state": "OPEN", "labels": [tal.L_SHIPPED]}
    tal.ref_delete = lambda key: None
    tal.local_unlock = lambda key: None
    tal.session_id = lambda: "revw0000cccc"
    tal.gh = lambda *a, **k: type("R", (), {"stdout": "", "stderr": "", "returncode": 0})()
    tal.gh_json = lambda args, default=None: (
        {"state": "CLOSED", "mergedAt": None, "headRefOid": "abc"}
        if "state,mergedAt,headRefOid" in args else default)

    class A:
        pr = 9002
        verdict = "pass"
        body = "ok"
        body_file = None
        allow_self = False

    try:
        tal.cmd_review_verdict(A())
        failed = None
    except tal.Fail as e:
        failed = str(e)

    check(failed is not None, "vẫn từ chối verdict trên PR đóng", str(failed)[:200])
    check(labels == [], "không gắn lại ready", str(labels))
    check(any("bỏ qua reset" in w for w in written), "ghi sổ bỏ qua", str(written))
    check(all("queued" not in w or "bỏ qua" in w for w in written), "không ghi queued", str(written))

def test_2300_ref_exists_three_states():
    print("ref_exists: True / False-404-thật / RAISE khi không đo được (#2300 A13)")

    def gh_404(args, check=True, stdin=None):
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "gh: Not Found (HTTP 404)"})()

    def gh_flake(args, check=True, stdin=None):
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "API rate limit exceeded"})()

    tal.gh = gh_404
    check(tal.ref_exists("issue-9") is False, "404 thật → False")
    tal.gh = gh_flake
    try:
        tal.ref_exists("issue-9")
        check(False, "quota cạn phải RAISE, không phải False")
    except tal.Fail as e:
        check("KHÔNG ĐO ĐƯỢC" in str(e), "nói rõ là không đo được", str(e)[:80])

def test_2300_ref_delete_reports():
    print("ref_delete: 404 = đã mất (True); lỗi khác = False + warn (#2300 A10)")
    warns = []
    tal.warn = lambda m: warns.append(m)
    tal.gh = lambda args, check=True, stdin=None: type(
        "R", (), {"returncode": 1, "stdout": "", "stderr": "Reference does not exist"})()
    check(tal.ref_delete("issue-9") is True, "ref vốn không tồn tại → True (đã mất)")
    tal.gh = lambda args, check=True, stdin=None: type(
        "R", (), {"returncode": 1, "stdout": "", "stderr": "API rate limit exceeded"})()
    check(tal.ref_delete("issue-9") is False, "xoá fail thật → False")
    check(any("KHÔNG xoá được" in w for w in warns), "và warn nói to", str(warns))

def test_2300_set_state_labels_safe_and_preserve():
    print("set_state_labels: đọc hỏng → BỎ lần ghi; preserve giữ nhãn review (#2300 A8/D4)")
    calls = []

    def gh_fail(args, check=True, stdin=None):
        calls.append(args)
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()

    warns = []
    tal.warn = lambda m: warns.append(m)
    tal.gh = gh_fail
    tal.set_state_labels(9, {tal.L_WORKING})
    check(not any("PUT" in " ".join(a) for a in calls), "GET fail → KHÔNG PUT", str(calls))
    check(any("BỎ lần ghi" in w for w in warns), "warn nói rõ vì sao bỏ")

    puts = []

    def gh_ok(args, check=True, stdin=None):
        if "-X" in args and "PUT" in args:
            puts.append(stdin)
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        return type("R", (), {"returncode": 0,
                              "stdout": json.dumps([tal.L_PASSED, "bug", tal.L_AWAIT]),
                              "stderr": ""})()

    tal.gh = gh_ok
    tal.set_state_labels(9, {tal.L_WORKING}, preserve={tal.L_PASSED, tal.L_AWAIT})
    final = json.loads(puts[0])["labels"]
    check(tal.L_PASSED in final and tal.L_AWAIT in final and tal.L_WORKING in final and "bug" in final,
          "preserve giữ nhãn review qua lần ghi của claim", str(final))

    puts.clear()
    tal.set_state_labels(9, {tal.L_WORKING})
    final = json.loads(puts[0])["labels"]
    check(tal.L_PASSED not in final, "không preserve → nhãn MANAGED bị thay như cũ", str(final))

def test_2300_release_refuses_foreign_and_cwd_mismatch():
    print("release: không nhả lease người khác; --issue tường minh thắng CWD (#2300 A1/A3)")
    # A3 — lease sống của session khác
    tal.session_id = lambda: "me-1234567"
    tal.ledger_read = lambda issue: (
        {"issue": issue, "group": [issue], "state": "executing",
         "lease": {"session": "other-999", "keys": [f"issue-{issue}"], "ttl": 2700,
                   "expires_at": "x"}, "history": []}, 1, tal.now())
    deleted = []
    tal.ref_delete = lambda k: deleted.append(k)
    tal.ledger_write = lambda led, cid, note=None: check(False, "KHÔNG được ghi sổ khi từ chối")
    try:
        tal.release(50, "queued", set(), "note")
        check(False, "phải từ chối")
    except tal.Fail as e:
        check("other-99" in str(e) and deleted == [], "nêu đúng chủ + không xoá gì", str(e)[:120])

    # A1 — thẻ CWD thuộc issue KHÁC --issue
    tal.lease_file = lambda *a, **k: (Path("/tmp"), {"issue": 2050})
    released = []
    tal.release = lambda issue, *a, **k: released.append(issue)

    class A:
        issue = 2162
        state = "abandon"
        note = "x"

    try:
        tal.cmd_release(A())
        check(False, "lệch thẻ/tham số phải DỪNG")
    except tal.Fail as e:
        check("2162" in str(e) and "2050" in str(e) and released == [],
              "nói rõ hai con số, không release gì", str(e)[:160])

def test_2300_requeue_contract():
    print("tal requeue: đường chính danh mở dead-letter (#2300 D3)")
    written = []
    labelled = []
    tal.issue_data = lambda n: {"number": n, "state": "open", "labels": [tal.L_DEAD, tal.L_BLOCKED]}
    tal.ledger_read = lambda n: ({"issue": n, "group": [n], "state": "dead_letter",
                                  "review_rounds": 3, "reaps": 2, "attempts": 9,
                                  "lease": None, "history": []}, 1, tal.now())
    tal.ledger_write = lambda led, cid, note=None: (written.append(json.loads(json.dumps(led))), 1)[1]
    tal.set_state_labels = lambda n, desired, drop=None, preserve=None: labelled.append((n, desired))
    tal.ref_exists = lambda k: False

    class A:
        issue = 77
        note = "root cause đã rõ"
        json = False

    out = tal.cmd_requeue(A())
    check(written and written[0]["state"] == "queued" and written[0]["review_rounds"] == 0
          and written[0]["reaps"] == 0 and written[0]["attempts"] == 9,
          "reset rounds/reaps, GIỮ attempts", str(written[0])[:160])
    check(labelled and tal.L_READY in labelled[0][1], "gắn lại agent:ready", str(labelled))

    class ANoNote:
        issue = 77
        note = ""
        json = False

    try:
        tal.cmd_requeue(ANoNote())
        check(False, "thiếu note phải Fail")
    except tal.Fail as e:
        check("--note" in str(e), "nói rõ thiếu note")

    tal.ref_exists = lambda k: True

    class A2:
        issue = 77
        note = "x"
        json = False

    try:
        tal.cmd_requeue(A2())
        check(False, "ref sống phải BUSY")
    except tal.Fail as e:
        check(e.code == tal.BUSY, "mã BUSY", str(e.code))

def test_2300_gc_keeps_unpushed_commits():
    print("cmd_gc: rào 'còn thứ chưa tới base' đứng TRƯỚC nhánh xoá (#2300 A12 / #2674)")
    src = TAL_SRC.read_text()
    blk = src[src.index("def cmd_gc("):]
    blk = blk[:blk.index("\ndef ", 10)]
    # Ghim VỊ TRÍ ở đây; ghim HÀNH VI ở test_gc_keeps_a_worktree_by_content_not_by_sha_ancestry.
    # Rào phải chạy TRƯỚC khi `remove_worktree` gọi `branch -D` — bản sao cuối cùng.
    # Neo vào TÊN HÀM, không vào danh sách tham số: bản trước ghim nguyên chuỗi
    # `worktree_unmerged_content(wt, BASE_BRANCH)` và đứt ngay khi #2792 thêm
    # `merged_head_sha=`. Bài này đo THỨ TỰ, nên chữ ký hàm không phải việc của
    # nó — ghim chữ ký ở đây chỉ bắt người thêm tham số phải sửa một rào không
    # liên quan, và lần sau họ sẽ nới nó ra cho xong.
    check("worktree_unmerged_content(" in blk,
          "gc hỏi 'còn nội dung nào chưa tới base'")
    check(blk.index("worktree_unmerged_content(")
          < blk.index('"xoá worktree + branch cục bộ'),
          "phép đo đứng TRƯỚC nhánh xoá")
    # Ratchet #2674: phép đo cũ hỏi TỔ TIÊN THEO SHA, mà repo này squash-merge nên
    # nó đúng với 100% worktree gc gặp — đừng dựng lại nó ở chỗ này.
    check('f"origin/{BASE_BRANCH}..HEAD"' not in blk,
          "KHÔNG quay lại đo tổ tiên SHA trong gc (#2674)")

def test_2993_gc_abandoned_refuses_when_branch_still_carries_content():
    print("#2993 ĐƯỜNG THẬT: nhánh còn nội dung chưa vào base ⇒ KHÔNG xoá ref")

    # Ghim HÀNH VI, không ghim chữ. Bản trước quét nguồn nên tắt rào bằng
    # `if False and ...` vẫn xanh cả 138 ca — rào bị tắt hoàn toàn mà không ai
    # biết. Đây là cùng khuôn với ca ở #2988.
    go, calls = _gc_abandoned_harness(keep_reason="còn 2 commit chưa tới dev")
    go()

    check(_deleted_refs(calls) == [], "KHÔNG xoá ref nào", str(_deleted_refs(calls)))
    restore_tal()

def test_2993_gc_abandoned_still_deletes_a_branch_that_holds_nothing():
    print("#2993 nhánh không còn gì riêng ⇒ dọn y như hôm nay (rào phải biết IM)")

    go, calls = _gc_abandoned_harness(keep_reason=None)
    go()

    check(any("refs/heads/issue-2993" in d for d in _deleted_refs(calls)),
          "vẫn xoá nhánh đã hợp nhất hết", str(calls))
    restore_tal()

def test_config_surface_is_wired_not_decorative():
    print("agent-loop.json điều khiển hằng số (#2348)")

    import json as _json
    import tempfile

    # Trước #2348 file config khai 12 khoá mà `tal` chỉ đọc 4. Một repo khác sửa
    # `labels.ready` sẽ không thấy tác dụng gì và không có gì báo cho họ biết —
    # đúng loại "rào rỗng" trả lời CÓ cho câu hỏi "chỗ này cấu hình được chưa".
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".claude").mkdir()
        (root / ".claude" / "agent-loop.json").write_text(_json.dumps({
            "baseBranch": "trunk",
            "promotionBranch": "release",
            "ttlSeconds": 111,
            "maxAttempts": 9,
            "refNamespace": "refs/other/leases/",
            "severityOrder": ["blocker", "major"],
            "labels": {"ready": "bot:go", "changesRequested": "bot:fix"},
        }))
        cwd0 = os.getcwd()
        try:
            os.chdir(root)
            fresh = load_tal()
        finally:
            os.chdir(cwd0)

    check(fresh.BASE_BRANCH == "trunk", "baseBranch từ config", fresh.BASE_BRANCH)
    check(fresh.PROMOTION_BRANCH == "release", "promotionBranch từ config", fresh.PROMOTION_BRANCH)
    check(fresh.TTL == 111, "ttlSeconds từ config", str(fresh.TTL))
    check(fresh.MAX_ATTEMPTS == 9, "maxAttempts từ config", str(fresh.MAX_ATTEMPTS))
    check(fresh.REF_NS == "refs/other/leases/", "refNamespace từ config", fresh.REF_NS)
    check(fresh.L_READY == "bot:go", "labels.ready từ config", fresh.L_READY)
    check(fresh.L_CHANGES == "bot:fix", "labels.changesRequested từ config", fresh.L_CHANGES)
    check(fresh.SEVERITY_RANK == {"blocker": 0, "major": 1},
          "severityOrder từ config", str(fresh.SEVERITY_RANK))

    # Khoá KHÔNG khai phải rơi về mặc định, không thành None/rỗng — một nửa config
    # thiếu là chuyện thường ở repo mới.
    check(fresh.L_SHIPPED == "status:shipped", "khoá thiếu → mặc định", fresh.L_SHIPPED)

    # Không có file config nào ⇒ vẫn chạy được bằng mặc định (repo chưa cài).
    with tempfile.TemporaryDirectory() as td:
        cwd0 = os.getcwd()
        try:
            os.chdir(td)
            bare = load_tal()
        finally:
            os.chdir(cwd0)
    check(bare.BASE_BRANCH == "dev" and bare.L_READY == "agent:ready",
          "không có agent-loop.json → mặc định, không nổ")

    sys.modules["tal"] = tal          # trả module về bản thật cho các ca sau

def test_config_command_exists_and_reports_sources():
    print("tal config (#2348 — Bước 0 của cả hai skill gọi lệnh này)")

    # Lệnh này TỪNG KHÔNG TỒN TẠI: `tal config` trả `argparse: invalid choice`,
    # trong khi cả `issue-work` lẫn `issue-review` bảo chạy nó trước khi sửa dòng
    # đầu tiên. Ca này ghim sự tồn tại của nó.
    check(callable(getattr(tal, "cmd_config", None)), "cmd_config tồn tại")

    import io
    from contextlib import redirect_stdout

    class A:
        json = True

    buf = io.StringIO()
    with redirect_stdout(buf):
        tal.cmd_config(A())
    import json as _json
    out = _json.loads(buf.getvalue())

    for key in ("values", "sources", "labels", "policyDocs", "riskDomains"):
        check(key in out, f"tal config --json có `{key}`")

    # Cột NGUỒN là phần quan trọng nhất: nó cho biết khoá vừa sửa có tác dụng không.
    check(set(out["sources"].values()) <= {"config", "mặc định"} or
          any(s.startswith("env ") for s in out["sources"].values()),
          "mỗi giá trị khai rõ nguồn env/config/mặc định", str(out["sources"]))

def test_no_test_name_is_defined_twice():
    """18 hàm `test_2300_*` từng nằm trong file này HAI LẦN — một khối 501 dòng
    bị dán lặp.

    `discover_tests()` đọc `globals()`, mà `def` sau ghi đè `def` trước, nên 18
    khối đầu **không bao giờ chạy**. Hôm phát hiện thì 17 cặp giống hệt nhau và
    cặp thứ 18 chỉ khác một khối comment ở cuối — nên chưa ca nào âm thầm mất
    hiệu lực. Đó là MAY, không phải thiết kế: sửa nhầm bản trên rồi thấy suite
    xanh là tin mình đã canh, đúng họ #2202 (*"một bài test tồn tại, trông như
    đã canh, và không bao giờ nổ thì TỆ HƠN không có test"*).

    `MIN_TESTS` không bắt được: nó đếm tên DUY NHẤT (`globals()` đã gộp), nên
    dán trùng cả trăm hàm cũng không làm con số nhúc nhích.

    Đọc NGUỒN chứ không đọc `globals()` — đó là điểm của bài này: `globals()`
    chính là chỗ bản trùng biến mất.
    """
    print("tal_test.py: không tên `test_*` nào được định nghĩa hai lần (#2682)")

    # `Path(__file__)`, KHÔNG phải `HERE / "tal_test.py"`: ca #2202 chạy một BẢN
    # SAO của file này ở thư mục tạm với tên khác, nơi `HERE` trỏ vào thư mục tạm
    # và `tal_test.py` không tồn tại. Bản đầu viết theo `HERE` làm suite CON chết
    # bằng FileNotFoundError trước khi canary kịp chạy — tức bài #2202 đỏ vì lý do
    # sai, và bài này thì không đo gì cả ở đó.
    src = Path(__file__).read_text(encoding="utf-8")
    seen: dict[str, list[int]] = {}
    for m in re.finditer(r"^def (test_\w+)\(", src, re.M):
        seen.setdefault(m.group(1), []).append(src[: m.start()].count("\n") + 1)

    dupes = {name: lines for name, lines in seen.items() if len(lines) > 1}
    check(dupes == {},
          "mỗi tên `test_*` chỉ định nghĩa MỘT lần",
          "; ".join(f"{n} ở dòng {ls}" for n, ls in sorted(dupes.items())) or "sạch")

    # Và bài này chỉ có nghĩa khi nó thật sự nhìn thấy các hàm — một regex hỏng
    # cũng cho `dupes == {}`. Số tên đọc từ NGUỒN phải khớp số hàm `discover_tests()`
    # nhặt được từ `globals()`; lệch nghĩa là một trong hai phía đang mù.
    check(len(seen) == len(discover_tests()),
          "số hàm đọc từ nguồn khớp số hàm suite thật sự chạy",
          f"nguồn {len(seen)} · globals {len(discover_tests())}")

def test_status_table_carries_addr_column():
    """#2704 — cột phải có TRONG bảng, không chỉ có hàm tính nó.

    Một helper đúng mà không ai in ra thì người bị chặn vẫn phải đi rải tin —
    tức vẫn đúng nguyên vấn đề ban đầu.
    """
    src = TAL_SRC.read_text(encoding="utf-8")

    check("'addr':<30" in src,
          "header của `tal status` có cột addr")
    check("r.get('addr'" in src,
          "dòng in của `tal status` đọc addr từ mỗi hàng")
    check(src.count('"agent_pid": agent_pid()') == 2,
          "cả lease issue LẪN lease review đều ghi agent_pid",
          f"đếm được {src.count(chr(34)+'agent_pid'+chr(34)+': agent_pid()')}")

def test_review_queue_reports_humans_separately():
    print("`review-queue` in rổ `humans` riêng và KHÔNG tính nó vào 'rỗng THẬT' (#2760)")

    src = TAL_SRC.read_text()
    blk = src[src.index("def cmd_review_queue("):]
    blk = blk[:blk.index("\ndef ", 10)]

    check('"humans": humans' in blk,
          "JSON có khoá `humans` — người gọi máy đọc được, không phải chỉ in ra")
    check("orphans if pr_is_agent_authored(author) else humans" in blk,
          "phân rổ đi qua hàm thuần đã test hai chiều, không so chuỗi tại chỗ")
    check("not out and not claimed and not orphans" in blk
          and "not humans" not in blk.split("rỗng THẬT")[0][-200:],
          "`humans` KHÔNG chặn câu 'rỗng THẬT' — PR của người không phải việc của "
          "vòng lặp, còn nó mà báo hết việc là ĐÚNG")

def test_config_prints_agent_logins():
    print("`tal config` in `agentLogins` — khoá được ĐỌC thì phải NHÌN THẤY (#2348)")

    # #2348: tám khoá từng được khai mà không khoá nào được đọc, và không có cách
    # nào nhìn ra ngoài việc đọc mã `tal`. Chiều ngược cũng phải chặn: một khoá
    # ĐƯỢC đọc nhưng không in ra thì sai chính tả trong config vẫn vô hình.
    src = TAL_SRC.read_text()
    blk = src[src.index("def cmd_config("):]
    blk = blk[:blk.index("\ndef ", 10)]

    check('"agentLogins": sorted(AGENT_LOGINS)' in blk,
          "nhánh --json có khoá `agentLogins` (giá trị ĐÃ phân giải, không phải raw)")
    check("agentLogins (" in blk,
          "nhánh in cho người cũng có, kèm số lượng")
    chunks = blk.split("agentLogins (")
    check(len(chunks) > 1 and "chưa khai" in chunks[1][:400],
          "rỗng thì nói rõ hệ quả, đừng in một dòng trống để người đọc tự đoán "
          "(dùng [1:2]/len chứ không [1] — khối biến mất phải FAIL sạch, không IndexError)")

def test_2782_gc_fetches_origin_base_before_measuring():
    print("cmd_gc fetch origin/<base> TRƯỚC khi đo unmerged (#2782)")
    src = TAL_SRC.read_text()
    blk = src[src.index("def cmd_gc("):]
    blk = blk[:blk.index("\ndef ", 10)]
    fetch = 'run(["git", "fetch", "-q", "origin", BASE_BRANCH]'
    check(fetch in blk, "cmd_gc fetch origin/<base> trước khi đo")
    check(blk.index(fetch) < blk.index("worktree_unmerged_content"),
          "fetch đứng TRƯỚC phép đo unmerged — gỡ dòng fetch thì bài này ĐỎ")
    check("worktree_paths_for_issue" in blk,
          "gc hỏi git worktree list, không đoán `.claude/worktrees/issue-N` (#2710)")

def test_2710_remove_worktree_does_not_claim_success_when_branch_remains():
    print("remove_worktree: branch còn thì KHÔNG khai đã xoá (#2710)")
    src = TAL_SRC.read_text()
    blk = src[src.index("def remove_worktree("):]
    blk = blk[:blk.index("\ndef ", 10)]
    check("KHÔNG khai đã xoá" in blk,
          "thất bại xoá branch/worktree phải nói ra, không nuốt stderr")
    check("worktree_paths_for_issue" in blk,
          "xoá theo đường dẫn git worktree list, không chỉ `.claude/worktrees/`")
    check('["git", "branch", "-D"' in blk,
          "xoá branch bằng -D (không -d so HEAD cây chính)")

def test_merge_uses_merge_commit_so_ancestry_holds():
    print("#2988 phép đo gắn với --merge; đổi sang --squash phải sửa cả hai vế")

    src = TAL_SRC.read_text(encoding="utf-8")
    # Đổi sang `--squash` thì nội dung vào base dưới SHA KHÁC, và rào ancestry
    # sẽ kêu oan MỌI lượt merge — rào kêu oan không bị tranh luận, nó bị TẮT.
    assert '"pr", "merge", str(pr), "-R", C.repo, "--merge"' in src, (
        "đường merge không còn dùng `--merge` — rào ancestry của #2988 phải được "
        "sửa cùng lúc, nếu không nó chặn nhầm mọi lượt merge hợp lệ"
    )
    print("  ok   --merge còn nguyên")

def test_hook_guard_command_patterns_run_without_a_lease():
    """#3545 — rào theo MẪU LỆNH phải chạy KỂ CẢ ngoài worktree có lease.

    Bản trước thoát sớm bằng `if context is None: sys.exit(0)` đặt ngay trên
    khối Bash, nên mọi rào mẫu lệnh chỉ sống bên trong một worktree issue —
    trong khi comment ngay trên nó khẳng định chúng "vẫn áp cho mọi lệnh Bash".
    Đo bằng payload thật từ một thư mục KHÔNG có lease: `git push origin dev`
    đi qua, exit 0.

    Bài này nạp payload và đọc `permissionDecision` — KHÔNG đọc regex. Một bài
    quét nguồn sẽ xanh với bất kỳ chỗ nào còn nhắc `DANGER_RE`, kể cả khi dòng
    gọi nó đã nằm sau một `sys.exit`.
    """
    print("cmd_hook_guard: rào mẫu lệnh chạy ngoài lease + `gh pr merge` đỏ bị chặn (#3545)")

    import contextlib
    import io

    def guard(cmd, cwd) -> str:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd},
                              "session_id": "s", "cwd": cwd})
        out, old = io.StringIO(), sys.stdin
        sys.stdin = io.StringIO(payload)
        try:
            with contextlib.redirect_stdout(out):
                try:
                    tal.cmd_hook_guard(None)
                except SystemExit:
                    pass
        finally:
            sys.stdin = old
        raw = out.getvalue().strip()
        if not raw:
            return ""
        return json.loads(raw)["hookSpecificOutput"]["permissionDecisionReason"]

    with tempfile.TemporaryDirectory() as td:
        # Thư mục KHÔNG có thẻ lease ở bất kỳ cấp cha nào — đúng hình dạng "gốc
        # repo", nơi mọi lượt `gh pr merge` của một session thật được gõ.
        bare = Path(td) / "no-lease"
        bare.mkdir()
        # `lease_file` NÉM `Fail` khi không thấy thẻ (không trả None) — chính vì
        # thế `cmd_hook_guard` bọc nó trong try/except. Fixture phải khẳng định
        # đúng điều đó, nếu không bài này lặng lẽ đo lại ca "có lease".
        try:
            tal.lease_file(bare, search=False)
            raise AssertionError("fixture hỏng: thư mục này phải KHÔNG có lease")
        except tal.Fail:
            pass

        check("push thẳng vào dev/main" in guard("git push origin dev", str(bare)),
              "git push origin dev NGOÀI lease → CHẶN")
        check("push thẳng vào dev/main" in guard("git push origin main", str(bare)),
              "git push origin main NGOÀI lease → CHẶN")

        # Không được NHỐT: lệnh thường và chính lệnh mà thông điệp mách phải chạy.
        for ok in ("pwd", "ls -la", "git status", "tal claim 1", "tal queue",
                   "git push origin issue-3545"):
            check(guard(ok, str(bare)) == "", f"NGOÀI lease vẫn CHO QUA: {ok}")


        # ── #3545 — rao KHONG duoc bao oan THAN heredoc ──────────────────────
        #
        # Rao mau lenh xet ca chuoi lenh, ma `git commit -F - <<'MSG' ... MSG`
        # mang nguyen thong diep trong do. Ca nay bat duoc bang chinh commit cua
        # ban sua: no trich mot lenh push-thang-dev de giai thich rao chan cai
        # gi, va bi chinh rao tu choi.
        #
        # Rao bao OAN thi bi TAT, khong bi tranh luan — va o day nguoi dau tien
        # no bao oan la nguoi dang viet tai lieu cho no.
        GP = 'git push origin dev'
        GM = 'gh pr merge 11 --squash'
        check(guard(GP, str(bare)) != "", "lenh THAT van CHAN")
        check(guard("git commit -F - <<'MSG'\nmo ta: " + GP + " bi chan\nMSG",
                    str(bare)) == "",
              "cung chuoi do trong THAN heredoc → CHO QUA (khong bao oan)")
        check(guard("cat <<'EOF'\n" + GP + "\n", str(bare)) == "",
              "heredoc CHUA DONG → than keo toi het lenh, van CHO QUA")
        check(guard("cat <<'EOF'\nvo hai\nEOF\n" + GP, str(bare)) != "",
              "lenh THAT dung SAU heredoc da dong → van CHAN (khong nuot qua tay)")
        check(guard("git commit -F - <<'M'\nnhac " + GM + "\nM", str(bare)) == "",
              "`gh pr merge` nhac trong than heredoc → CHO QUA")

        # ── `gh pr merge` ────────────────────────────────────────────────────
        calls = []

        def fake_checks(pr):
            calls.append(pr)
            return {
                11: ("fail", ["arch-gate=pass", "version · drift · guard tests=fail"]),
                22: ("pending", ["pest=pending"]),
                33: ("pass", ["arch-gate=pass"]),
            }[pr]

        orig = tal.pr_checks
        tal.pr_checks = fake_checks
        try:
            red = guard("gh pr merge 11 --squash", str(bare))
            check("CI ĐỎ trên PR #11" in red, "merge PR có check ĐỎ → CHẶN")
            check("version · drift · guard tests" in red,
                  "thông điệp gọi TÊN check đã đỏ, không đổ cả bảng")

            pend = guard("gh pr merge 22 --squash --delete-branch", str(bare))
            check("CHƯA XONG" in pend, "merge khi CI chưa xong → CHẶN (#2669)")
            check("pest" in pend, "thông điệp gọi tên check còn chạy")

            check(guard("gh pr merge 33 --squash", str(bare)) == "",
                  "CI XANH → CHO QUA (chặn mọi `gh pr merge` là sai: promote "
                  "dev→main và PR của session khác vẫn cần lệnh này)")

            # Dạng có `-R owner/repo` xen giữa — session thật hay gõ kiểu này.
            check("CI ĐỎ trên PR #11" in guard("gh pr merge -R o/r 11 --squash", str(bare)),
                  "dạng `-R owner/repo` cũng bị bắt")

            # Vế đối chứng: rào phải THẬT SỰ hỏi CI, không chỉ khớp chuỗi rồi
            # đoán. Không có lượt gọi nào nghĩa là nó chặn/cho qua theo văn bản.
            check(calls == [11, 22, 33, 11],
                  f"mỗi lượt merge phải HỎI pr_checks đúng một lần; đã gọi: {calls}")
        finally:
            tal.pr_checks = orig


def _git(*args: str) -> None:
    tal.run(["git", *args])


def _init_repo(path: Path, origin: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", str(path))
    _git("-C", str(path), "config", "user.email", "tal-test@example.com")
    _git("-C", str(path), "config", "user.name", "tal test")
    _git("-C", str(path), "config", "commit.gpgsign", "false")
    _git("-C", str(path), "remote", "add", "origin", origin)
    (path / "README.md").write_text("x\n")
    _git("-C", str(path), "add", "README.md")
    _git("-C", str(path), "commit", "-q", "-m", "init")


def _tiny_go_module(root: Path, *, embed_missing_dir: bool, broken: bool) -> None:
    """Dựng một module Go tí hon để cổng chạy `go` THẬT lên nó."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "go.mod").write_text("module tinygate\n\ngo 1.21\n")
    embed = ""
    if embed_missing_dir:
        # y hệt workstation-app/frontend.go: trỏ vào thư mục artifact KHÔNG có trong git
        embed = ('import "embed"\n\n//go:embed all:frontend/dist\n'
                 'var assets embed.FS\n\nvar _ = assets\n')
    body = "func Hello() int { return 1 }\n" if not broken else "func Hello() int { return }\n"
    (root / "main.go").write_text("package tinygate\n\n" + embed + "\n" + body)


def _adopt_world(td, owner, epoch=7, ref_alive=True):
    """Dựng một thế giới nhỏ cho `cmd_adopt`: sổ + ref + worktree, không mạng."""
    root = Path(td)
    wt = root / ".claude" / "worktrees" / "issue-2238"
    wt.mkdir(parents=True)
    state = root / "state"
    state.mkdir()

    class FakeCtx:
        repo = "o/r"
        main_worktree = root
        worktrees_dir = root / ".claude" / "worktrees"
        state_dir = state

    tal.C = FakeCtx()

    led = {"issue": 2238, "group": [2238], "branch": "issue-2238", "state": "executing",
           "epoch": epoch, "attempts": 1, "review_rounds": 0, "reaps": 0, "pr": None,
           "history": [],
           "lease": {"key": "issue-2238", "keys": ["issue-2238"], "epoch": epoch,
                     "session": owner, "host": "h", "ttl": 2700,
                     "acquired_at": "2026-08-09T00:00:00Z",
                     "expires_at": "2026-08-09T00:45:00Z"}}

    writes: list = []
    server_clock = tal.now()          # sổ trả đồng hồ SERVER, không phải chuỗi
    tal.ledger_read = lambda n: (led, 5226320939, server_clock)
    tal.ledger_write = lambda d, cid, note=None: writes.append(note) or cid
    tal.lease_expired = lambda d, upd: False
    tal.ref_exists = lambda k: ref_alive
    tal.refs_all = lambda: ["issue-2238", "pr-9"]
    tal.local_lock = lambda k: True
    tal.ensure_worktree = lambda issue, branch: wt
    tal.assert_worktree_attached = lambda p: None
    return wt, led, writes


def _region_world(holders: dict[int, dict]):
    """Dựng thế giới giả cho rào vùng: `refs_all` + `ledger_read` + đồng hồ.

    `holders` = {issue: {"session":…, "regions":[…], "expired": bool}}. Đi đúng
    hai hàm mà bản thật đọc, nên test đo hành vi chứ không đo lại chính nó.
    """
    tal.refs_all = lambda: [f"issue-{n}" for n in holders] + ["pr-99", "merge-batch"]

    def _read(n):
        h = holders.get(n)
        if h is None:
            return {"issue": n, "lease": None}, 1, tal.now()
        return ({"issue": n, "lease": {"session": h["session"], "ttl": 2700,
                                       "host": "box", "regions": h["regions"]}},
                1, tal.now())

    tal.ledger_read = _read
    tal.lease_expired = lambda d, upd: bool(
        (holders.get(d.get("issue"), {}) or {}).get("expired"))


def _gh_stub_with_head(calls=None, head="feed0000face1111beef2222"):
    """Stub `gh` biết trả `headRefOid` — `cmd_merge` đo nó TRƯỚC khi merge (#2988)."""
    def fake(args, check=True, stdin=None):
        if calls is not None:
            calls.append(args)
        out = '{"headRefOid":"%s"}' % head if "headRefOid" in args else ""
        return type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})()
    return fake


def _run_stub_ancestor(ok: bool, seen=None):
    """Stub `run` chỉ điều khiển `merge-base --is-ancestor` (#2988)."""
    def fake(cmd, cwd=None, check=True, stdin=None):
        if seen is not None:
            seen.append(cmd)
        rc = 0 if ("--is-ancestor" not in cmd or ok) else 1
        return type("R", (), {"returncode": rc, "stdout": "", "stderr": ""})()
    return fake


def _gc_abandoned_harness(*, keep_reason, remote_branch=True, worktree=False):
    """Dựng `cmd_gc` chạy tới đúng nhánh 'PR đóng, KHÔNG merge'.

    → (chạy, danh sách lệnh gh). `keep_reason` là thứ phép đo nội dung trả về.
    """
    calls: list[list[str]] = []

    def fake_gh(args, check=True, stdin=None):
        calls.append(args)
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    def fake_gh_json(args, default=None):
        if "--state" in args and "closed" in args:
            return [{"number": 42, "headRefName": "issue-2993", "mergedAt": None}]
        return [] if isinstance(default, list) else (default or [])

    # `cmd_gc` hỏi git thật cho `main_worktree`; stub `run` trả rỗng nên phải
    # nạp sẵn cache của Ctx thay vì để nó đi dò.
    tal.Ctx._main = Path("/tmp/tal-gc-test")
    tal.Ctx._root = Path("/tmp/tal-gc-test")

    tal.gh = fake_gh
    tal.gh_json = fake_gh_json
    tal.gh_json_required = lambda args: fake_gh_json(args, [])
    tal.run = lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    tal.reap_batch_gate = lambda dry: []
    tal.reap_leases = lambda dry: []
    tal.cleanup_orphan_worktrees = lambda dry: []
    tal.delete_merged_branches = lambda repo, dry, protect: []
    tal.stranded_review_candidates = lambda *a, **k: []
    tal.branch_exists_remote = lambda br, cwd=None: remote_branch
    tal.branch_exists_local = lambda br: False
    tal.worktree_paths_for_issue = lambda i: ([tal.C.worktrees_dir / f"issue-{i}"]
                                              if worktree else [])
    tal.worktree_unmerged_content = lambda *a, **k: keep_reason
    tal.remove_worktree = lambda i: True

    class A:
        dry_run = False
        include_abandoned = True
        no_submodules = True
        json = False

    return (lambda: tal.cmd_gc(A())), calls


def _deleted_refs(calls) -> list[str]:
    return [" ".join(a) for a in calls
            if "DELETE" in a and any("refs/heads/" in x for x in a)]


def _merge_args(**kw):
    base = dict(pr=42, force=False, no_subs=True, self_merge=False, note=None,
                require_ci=False, batch_verified=False, json=False, promote=False,
                ci_red=False)
    base.update(kw)
    return argparse.Namespace(**base)


def _stub_merge_env(why, calls):
    """Dựng đủ để `cmd_merge` chạy tới CỬA CI rồi (nếu qua) tới `gh pr merge`."""
    class R:
        stdout, stderr, returncode = "", "", 0

    tal.gh_json = lambda args, default=None: {"baseRefName": "dev"}
    tal.gh = _gh_stub_with_head(calls)
    # #2988 — merge THẬT: head phải là tổ tiên của base, nếu không rào mới chặn.
    tal.run = _run_stub_ancestor(True)
    tal.ref_exists = lambda key: False
    tal.merge_blockers = lambda pr, require_ci=True: (None, list(why), ("abc123abc123", "9"))
    tal.pr_checks = lambda pr: ("fail", ["arch-gate=fail"]) if why else ("pass", [])
    tal.pr_dangling_pointers = lambda pr: []
    tal.session_id = lambda: "deadbeefcafe0000"
    # Chẩn đoán base đỏ đi ra mạng — test này đo RÀO, không đo chẩn đoán.
    tal.base_red_hint = lambda names: ""


def _stub_pending_blockers_env(rows):
    """Đủ để `merge_blockers` THẬT chạy tới phần CI, với bảng check là `rows`."""
    tal.gh_json = lambda args, default=None: (
        rows if args[:2] == ["pr", "checks"] else
        {"isDraft": False, "mergeable": "MERGEABLE", "state": "OPEN",
         "headRefName": "issue-1", "headRefOid": "abc123abc123", "labels": []})
    tal.pr_issue = lambda pr: 1
    tal.issue_data = lambda n: {"labels": [tal.L_PASSED]}
    tal.pr_verdict_pass_evidence = lambda pr, sha=None, head_branch=None: ("abc123abc123", "9")


def _squash_merge_fixture(root: Path, land_on_base: bool, base_moves_on: bool = False):
    """Dựng repo thật: `origin` bare + cây làm việc + một nhánh `issue-N`.

    `land_on_base=True` mô phỏng **squash-merge**: nội dung y hệt được ghi lên
    base bằng một commit MỚI (SHA khác) — đúng cách repo này merge.
    Trả về đường dẫn cây đang đứng trên nhánh.
    """
    up = root / "up.git"
    _git("init", "-q", "--bare", "-b", "main", str(up))

    wt = root / "wt"
    _init_repo(wt, str(up))
    _git("-C", str(wt), "push", "-q", "-u", "origin", "main")

    _git("-C", str(wt), "checkout", "-q", "-b", "issue-2606")
    (wt / "feature.txt").write_text("nội dung của nhánh\n")
    _git("-C", str(wt), "add", "feature.txt")
    _git("-C", str(wt), "commit", "-q", "-m", "feat: thêm feature.txt")

    if land_on_base:
        base = root / "base"
        _git("clone", "-q", str(up), str(base))
        _git("-C", str(base), "config", "user.email", "tal-test@example.com")
        _git("-C", str(base), "config", "user.name", "tal test")
        _git("-C", str(base), "config", "commit.gpgsign", "false")
        (base / "feature.txt").write_text("nội dung của nhánh\n")
        _git("-C", str(base), "add", "feature.txt")
        # Commit MỚI, thông điệp khác, SHA khác — chính là hình dạng squash.
        _git("-C", str(base), "commit", "-q", "-m", "feat: thêm feature.txt (#2606) (squash)")
        if base_moves_on:
            # base ĐI TIẾP sau khi merge — đây là ca #2616/#2640 trong issue: nội
            # dung file khác đi, nhưng không có gì của nhánh bị mất.
            (base / "feature.txt").write_text("nội dung của nhánh\nrồi dev sửa tiếp\n")
            _git("-C", str(base), "add", "feature.txt")
            _git("-C", str(base), "commit", "-q", "-m", "chore: dev đi tiếp trên cùng file")
        _git("-C", str(base), "push", "-q", "origin", "main")

    _git("-C", str(wt), "fetch", "-q", "origin")
    return wt


def _stub_ancestry(is_ancestor: bool) -> list[list[str]]:
    """Thay `run` để chỉ điều khiển đúng `merge-base --is-ancestor`."""
    cmds: list[list[str]] = []

    def fake_run(cmd, cwd=None, check=True, stdin=None):
        cmds.append(cmd)

        class R:
            stdout = ""
            stderr = ""
            returncode = 0 if ("--is-ancestor" not in cmd or is_ancestor) else 1
        return R()

    tal.run = fake_run

    return cmds


MIN_TESTS = 46


def discover_tests() -> list:
    """Mọi hàm `test_*` ở cấp module — đọc `globals()` TẠI THỜI ĐIỂM GỌI.

    Vì sao không liệt kê tay (#2202): `main()` từng lặp trên một tuple tên viết
    tường minh, nên một hàm `test_*` mới viết xong **không bao giờ chạy** mà suite
    vẫn in "tất cả pass". Đã cắn thật ở #2156 — nghi thức chiều ngược (gỡ bản sửa,
    đòi test ĐỎ) báo XANH cả hai chiều vì ba ca mới nằm ngoài tuple. Một bài test
    tồn tại, trông như đã canh, và không bao giờ nổ thì TỆ HƠN không có test: nó
    trả lời "rồi" cho câu hỏi "chỗ này canh chưa?".

    Bẫy thứ hai, cùng ca: các định nghĩa nằm SAU khối `if __name__ == "__main__"`
    thì chưa tồn tại lúc `main()` chạy. Ở đây tránh được vì `globals()` được đọc
    lúc GỌI, và lời gọi duy nhất nằm ở dòng CUỐI file — mọi `def` đã xong. Đừng
    dời khối `if __name__` lên giữa file; `MIN_TESTS` ở trên là cái sẽ bắt.
    """
    return [fn for name, fn in sorted(globals().items())
            if name.startswith("test_") and isinstance(fn, types.FunctionType)]
def main() -> int:
    tests = discover_tests()
    print(f"phát hiện {len(tests)} ca test (ngưỡng tối thiểu {MIN_TESTS})\n")
    if len(tests) < MIN_TESTS:
        print(f"HỎNG: chỉ phát hiện {len(tests)} ca test, kỳ vọng ít nhất {MIN_TESTS}. "
              f"Test đã bị xoá, hoặc `discover_tests()` không còn nhìn thấy chúng "
              f"(khối `if __name__` bị dời lên trước các `def`?). Suite này là cổng "
              f"của chính vòng lặp issue — không được im lặng co lại (#2202).")
        return 1
    for fn in tests:
        restore_tal()          # mỗi test bắt đầu từ `tal` NGUYÊN BẢN, không nhận rác của test trước
        try:
            fn()
        except Exception as e:
            # Một bài NỔ không được làm mù 45 bài còn lại. Trước đây exception thoát
            # thẳng ra `main()` nên suite dừng ngay tại đó và không ai biết phần sau
            # xanh hay đỏ — tức một bài hỏng che mất mọi bài sau nó.
            print(f"  FAIL {fn.__name__} — NỔ: {type(e).__name__}: {e}")
            FAILURES.append(f"{fn.__name__} (nổ)")
        print()
    if FAILURES:
        print(f"{len(FAILURES)} FAIL: " + ", ".join(FAILURES))
        return 1
    print(f"tất cả pass ({len(tests)} ca)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
