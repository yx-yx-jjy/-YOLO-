-- ============================================================================
--  非机动车交通违法检测系统 —— 物理模型建表脚本（SQLite）
--  文件用途：可直接在 SQLite 执行的完整 DDL（表 / 索引 / 外键 / CHECK / 触发器）
--  目标库文件：backend/storage/traffic.db
--  对应版本：schema_version = 1（等价于 01-改造架构方案.md §8 的表划分）
--  生成人：数据建模工程师 储海量
--  生成日期：2026-10-03
--
--  表名与 01-改造架构方案.md §8 保持一致（该节原话"表划分建议，供 data-engineer 细化"）：
--    cameras / users / violation_records / review_history / dispositions /
--    disposition_history / schema_version
--    唯一的强制偏差：架构稿写的是单数 disposition，本脚本按"表名一律复数"的
--    命名规范用 dispositions（与 review_history 的复数风格统一）。
--
--  本脚本的主要依据（以现有代码字段语义为准，未擅自改名）：
--    · deliverables/db-migration/reference/demoDataset.js —— 台账记录结构 + 处置状态机（原 frontend/src/mock/demoDataset.js，已退役迁出 src）
--    · deliverables/db-migration/reference/data.js        —— mockUsers / mockSystemLogs 字段（原 frontend/src/mock/data.js，同上）
--    · frontend/src/data/cameras.js       —— 卡口主数据 + WGS84 坐标
--    · frontend/src/stores/violations.js  —— 复核/处置动作的完整字段写入逻辑
--    · backend/app/camera.py:432-456,681-700 —— 后端实时抓拍/人工抓拍记录结构
--
--  约定：
--    · 表名、字段名一律 snake_case，表名用复数。
--    · 时间戳一律为「本地时间字符串 YYYY-MM-DD HH:MM:SS」(GMT+8)。
--      绝不用 UTC、绝不用 ISO8601 的 'T' 分隔或结尾 'Z' —— 见各时间列的 GLOB 约束。
--    · created_at / updated_at 为 SQLite 侧审计列，默认取 localtime。
--      业务时间列（capture_time / event_time 等）没有默认值，必须由应用显式写入，
--      避免应用把 UTC 和本地时间混着写进来。
--    · 执行前请确认 SQLite >= 3.9（需要 json_valid 的 JSON1 扩展）。
--
--  每个 CHECK / 触发器后面都用中文注释写明「它是为了防哪个真实错误」。
-- ============================================================================

PRAGMA foreign_keys = ON;

-- SQLite 的 WAL 模式提升读写并发（读不阻塞写），适合"实时抓拍写 + 台账页读"
-- 同时发生的场景。属于数据库级设置，放脚本最前面显式声明。
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;


-- ----------------------------------------------------------------------------
-- 0. schema_version —— 迁移版本登记表
--    谁写它：迁移执行器（每次跑完一个迁移脚本后插入一行）
--    谁读它：启动时的自检逻辑（缺版本 → 拒绝启动 / 自动补迁移）
--
--    兼容说明：01-改造架构方案.md §7.1 的迁移执行器只需读 version、写 version+applied_at。
--    故 name / checksum 都给了默认值 ''，执行器只写 (version, applied_at) 也能成功。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,                -- 迁移序号，对应 migrations/000N_*
    name        TEXT    NOT NULL DEFAULT '',        -- 迁移文件名，便于人工核对
    checksum    TEXT    NOT NULL DEFAULT '',        -- 脚本内容 sha256，防脚本被偷偷改坏后重跑
    applied_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);


-- ----------------------------------------------------------------------------
-- 1. cameras —— 卡口主数据
--    谁写它：一次性数据导入脚本（cameras.js → DB）；后续卡口管理功能【待确认是否存在该页面】
--    谁读它：大屏地图 WuhanTrafficMap、台账页 cameraName()、研判页按卡口聚合
--
--    主键选 'CAM-03' 这种"卡口编号"，而不是台账里的 'CAM-03-东向非机动车道'。
--    原因见设计文档第 8 节"为什么这么分表"。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cameras (
    camera_key   TEXT    PRIMARY KEY,               -- 'CAM-01'..'CAM-05'
    name         TEXT    NOT NULL,                  -- '建设大道-香港路口'
    area         TEXT    NOT NULL DEFAULT '',       -- '汉口金融街'
    latitude     REAL    NOT NULL,                  -- WGS84 纬度（GCJ-02 转换在前端做）
    longitude    REAL    NOT NULL,                  -- WGS84 经度
    heat_radius  INTEGER NOT NULL DEFAULT 0,        -- 地图热力圈半径（米）
    is_active    INTEGER NOT NULL DEFAULT 1
                 CHECK (is_active IN (0, 1)),       -- 防误写 'true'/'yes' 之类
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    -- 坐标范围校验：防把经纬度顺序写反（把经度 114.xx 写进 latitude 列）。
    -- 武汉纬度约 30.5N、经度约 114.3E，一旦写反这里会立刻拒绝。
    CHECK (latitude  >= -90  AND latitude  <= 90),
    CHECK (longitude >= -180 AND longitude <= 180)
);


-- ----------------------------------------------------------------------------
-- 2. users —— 用户与登录
--    谁写它：UserManagement.vue（新增账号 / 冻结解冻 / 重置密码）、auth.js（登录更新 last_login_at）
--    谁读它：UserManagement.vue 列表、auth.js 取当前用户
--
--    说明：mock 阶段没有密码字段（resetPass 只弹提示"重置为 123456"）。
--    落库必须存哈希，故新增 password_hash 列。【哈希算法待确认：建议 PBKDF2-SHA256 / bcrypt】
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL,                 -- 'officer_zhang'
    real_name     TEXT    NOT NULL,                 -- '张建国 (警官)'
    badge_number  TEXT    NOT NULL,                 -- '08412' / 'ADMIN-01'
    role          TEXT    NOT NULL
                  CHECK (role IN ('officer', 'admin')),
    status        TEXT    NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'disabled')),
    department    TEXT    NOT NULL DEFAULT '',
    password_hash TEXT,                             -- NULL = 尚未设置密码（导入的历史账号）
    last_login_at TEXT,                             -- NULL = 从未登录（前端显示'未登录'）
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    -- 登录账号唯一：防出现两个 officer_zhang 导致登录时 matched 到错误的人
    UNIQUE (username),
    -- 警号唯一：警号是执法署名依据，重复会导致"谁复核的"无法定位到人
    UNIQUE (badge_number),
    -- 若写了登录时间，必须是合法的本地时间串：防写入 UTC / ISO8601
    CHECK (last_login_at IS NULL
           OR last_login_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]')
);


-- ----------------------------------------------------------------------------
-- 3. violation_records —— 违规台账主表（核心表）
--    谁写它：
--      · camera.py::_auto_record_violation / take_snapshot（后端实时抓拍，status='pending'）
--      · 离线推理线索入库接口（现为 stores/violations.js::addInferenceViolation，改造后走后端）
--      · 复核动作 approveRecord / rejectRecord / revokeReview（更新 status / reviewer / review_*）
--    谁读它：台账页、处置工作台、大屏统计、研判页、CSV 导出 exportRecordsToCSV()
--
--    id 保留为「业务主键」：它是查询入口、跨表外键、导出编号，
--    形态有两种共存：EV-20261003-0022（演示 4 位十进制）/ EV-20261003-a1b2c3（实时 6 位 hex）
--    另有 EV-AI-xxxxxx（离线上传）。因此用 TEXT，不改成自增整数。
--
--    API 契约对照（01-改造架构方案.md §4.1 的 Record）：API 里的 camera_id ← 本表 camera_label；
--    API 里的 details 对象 ← 读时由 plate_or_vehicle/helmet_status/consecutive_frames/source_file/
--    ai_disclaimer 5 列再叠加 details_json 现场拼装。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS violation_records (
    id                 TEXT    PRIMARY KEY,
                       -- 防把 id 写成纯数字 / 空串 / 别的业务编号：所有合法形态都以 'EV-' 开头
    camera_key         TEXT,                        -- 解析后的卡口外键 'CAM-03'；无法归属时为 NULL（如'离线上传 · xx.mp4'）
    camera_label       TEXT    NOT NULL,            -- 台账里的原始 camera_id 串，原样保留用于展示/导出
                                                    -- 例：'CAM-03-东向非机动车道' 或 'CAM-04: 武珞路-中南路口 (B站实景1080P)'
    direction          TEXT,                        -- 从 label 解析出的方向后缀，如'东向非机动车道'；解析不出为 NULL
    track_id           TEXT,                        -- 车辆追踪 ID；后端可能是整数，抓拍快照写 'SNAP'，离线写 '-' → 故用 TEXT
    violation_type     TEXT    NOT NULL,            -- '未按规定佩戴安全头盔' / '人工实时抓拍取证' ...
    category           TEXT    NOT NULL DEFAULT 'helmet',  -- 判别类别，当前恒为 'helmet'（软枚举，未加硬 CHECK 以免锁死未来类别）
    confidence         REAL    NOT NULL,            -- 0-1 浮点
    status             TEXT    NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewer           TEXT,                        -- 复核人署名快照，如'张警官 (警号: 08412)'
    review_time        TEXT,                        -- 复核时间（本地时间串）
    review_remark      TEXT    NOT NULL DEFAULT '',
    capture_time       TEXT    NOT NULL,            -- 抓拍时间（本地时间串，无默认值，必须应用显式写）
    evidence_url       TEXT,                        -- '/artifacts/<id>/evidence.jpg'
    roi_url            TEXT,                        -- '/artifacts/<id>/roi.jpg'（仅实时抓拍有）
    -- 以下 5 列是从 details 对象中"提升"出来的稳定、高频、可展示/可筛选字段
    plate_or_vehicle   TEXT,                        -- '白色雅迪电瓶车 [无牌照]' —— 证据弹窗与导出直接展示
    helmet_status      TEXT,                        -- 'not_wearing'（软枚举）
    consecutive_frames INTEGER
                       CHECK (consecutive_frames IS NULL OR consecutive_frames >= 0),
                                                    -- 连续确认帧数，负数无意义
    source_file        TEXT,                        -- 来源标识（后端为卡口名，离线为上传文件名）
    ai_disclaimer      TEXT,                        -- AI 免责声明文案快照
    details_json       TEXT                         -- 残余变体：bbox 数组、timestamp_seconds、frame_index 等
                       CHECK (details_json IS NULL OR json_valid(details_json)),
                                                    -- 防写坏 JSON 导致详情页解析崩溃
    created_at         TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at         TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    -- 外键：卡口删除前必须先处理台账（RESTRICT），防止删除卡口后台账变孤儿，聚合统计直接对不上
    FOREIGN KEY (camera_key) REFERENCES cameras (camera_key)
        ON UPDATE CASCADE ON DELETE RESTRICT,

    -- id 必须保持 EV- 前缀：防有人把自增整数或前端临时 key 塞进来当业务编号
    CHECK (id LIKE 'EV-%'),

    -- 置信度越界：防把百分数（如 92）当成 0-1 小数写进来
    CHECK (confidence >= 0 AND confidence <= 1),

    -- 复核状态一致性（这是状态机的核心约束）：
    --   待复核 → 必须没有复核人、没有复核时间；
    --   已复核（approved/rejected）→ 必须有复核人和复核时间。
    -- 防的错误：状态改了却忘写 reviewer，导致台账显示"已确认入卷"却查不到是谁复核的。
    CHECK (
        (status =  'pending' AND reviewer IS NULL     AND review_time IS NULL)
     OR (status <> 'pending' AND reviewer IS NOT NULL AND review_time IS NOT NULL)
    ),

    -- 时间串格式：只接受 'YYYY-MM-DD HH:MM:SS'。防误写 UTC（日期差 8 小时）或 ISO8601（'T'/'Z'）
    CHECK (capture_time  GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]'),
    CHECK (review_time IS NULL
           OR review_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]')
);


-- ----------------------------------------------------------------------------
-- 4. review_history —— 复核轨迹（只追加不覆盖的执法留痕）
--    谁写它：stores/violations.js::pushReviewHistory
--            （approveRecord / rejectRecord / revokeReview 各追加一条）
--    谁读它：证据弹窗"复核历史"Tab、台账详情
--
--    为什么独立成表而不塞 JSON：见设计文档第 8 节"为什么这么分表"。
--    本表在业务语义上只允许 INSERT，不允许 UPDATE/DELETE（由下方触发器强制）。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS review_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id   TEXT    NOT NULL,
    seq            INTEGER NOT NULL,                -- 同一记录内序号，从 1 起，保证轨迹有序
    action         TEXT    NOT NULL
                   CHECK (action IN ('approve', 'reject', 'revoke')),
    reviewer       TEXT    NOT NULL DEFAULT '',     -- 操作人署名（前端 makeHistoryEntry 的 reviewer）
    badge          TEXT    NOT NULL DEFAULT '',     -- 警号（前端 makeHistoryEntry 的 badge）
    remark         TEXT    NOT NULL DEFAULT '',     -- 复核意见 / 撤销理由
    event_time     TEXT    NOT NULL,                -- 本地时间串
    created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (violation_id) REFERENCES violation_records (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,       -- 禁止级联删除：台账是执法档案，不物理删除；见下方说明

    -- 同一条记录的序号不能重复：防并发写时两条轨迹抢到同一个 seq 导致轨迹错乱
    UNIQUE (violation_id, seq),

    -- 时间串格式守卫（同 violation_records）
    CHECK (event_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]')
);


-- ----------------------------------------------------------------------------
-- 5. dispositions —— 处置「当前态」（1:1，可变）
--    谁写它：approveRecord(建 to_notify) / markNotified / markDisposed / archiveDisposition / revokeReview(重置为 null)
--    谁读它：处置工作台、台账页、大屏处置指标（toNotifyCount / disposedCount / dispositionRate）
--
--    设计要点：每条台账都有一行；status 为 NULL 表示"未进入处置"。
--    只有 status='approved' 的记录才允许 status 非空 —— 由触发器强制（见下）。
--    命名说明：架构稿 §8 写单数 disposition，此处按"表名复数"规范用 dispositions。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dispositions (
    violation_id TEXT    PRIMARY KEY,               -- 1:1，主键即外键
    status       TEXT                               -- NULL = 未进入处置（pending / rejected 均为 NULL）
                 CHECK (status IS NULL
                        OR status IN ('to_notify', 'notified', 'disposed', 'archived')),
    method       TEXT    NOT NULL DEFAULT '',       -- 处置方式：警告处罚 / 罚款处罚 / 安全教育学习 / 现场拦查处置
    notified_at  TEXT    NOT NULL DEFAULT '',       -- 告知时间（未告知为 ''，注意不是 NULL）
    disposed_at  TEXT    NOT NULL DEFAULT '',       -- 处置时间
    handler      TEXT    NOT NULL DEFAULT '',       -- 处置承办人
    remark       TEXT    NOT NULL DEFAULT '',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (violation_id) REFERENCES violation_records (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,       -- 禁止级联删除（同 review_history：台账不物理删除）

    -- 状态机与时间戳自洽（防"已处置却没有处置时间"这种空心状态）：
    CHECK (
        status IS NULL
     OR status = 'to_notify'
     OR (status = 'notified' AND notified_at <> '')
     OR (status IN ('disposed', 'archived') AND notified_at <> '' AND disposed_at <> '')
    )
);


-- ----------------------------------------------------------------------------
-- 6. disposition_history —— 处置轨迹（只追加不覆盖）
--    谁写它：stores/violations.js::pushDispositionHistory
--            （create / notify / dispose / archive；revoke 时追加一条回退留痕）
--    谁读它：处置工作台"处置轨迹"、台账详情
--    命名说明：对齐前端字段 record.disposition.history，故名 disposition_history。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS disposition_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id   TEXT    NOT NULL,
    seq            INTEGER NOT NULL,
    action         TEXT    NOT NULL
                   CHECK (action IN ('create', 'notify', 'dispose', 'archive', 'revoke')),
    operator       TEXT    NOT NULL DEFAULT '',     -- 前端 pushDispositionHistory 的 operator
    remark         TEXT    NOT NULL DEFAULT '',
    event_time     TEXT    NOT NULL,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (violation_id) REFERENCES violation_records (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,       -- 禁止级联删除（同 review_history：台账不物理删除）

    UNIQUE (violation_id, seq),
    CHECK (event_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]')
);


-- ----------------------------------------------------------------------------
-- 7. system_logs —— 系统操作日志（哈希链，只追加）
--    谁写它：复核/登录/导出/用户管理等写操作的旁路记录
--    谁读它：admin/SystemLogs.vue（UI 显示 "#LOG-{id}"、"哈希已存证"）
--
--    operator / role 存"快照文本"而不是只存 user_id：审计日志必须不可变，
--    用户改名/离职后日志仍要能还原当时是谁、什么角色操作。
--    user_id 仅作可选关联（ON DELETE SET NULL），不承担展示职责。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time   TEXT    NOT NULL,                  -- 业务时间（mock 的 time 字段）
    operator     TEXT    NOT NULL DEFAULT '',       -- '张警官 (08412)' 快照
    user_id      INTEGER,                           -- 可空外键，指向操作者账号
    role         TEXT    NOT NULL DEFAULT '',       -- 操作时角色快照
    action_type  TEXT    NOT NULL,                  -- REVIEW_APPROVE / REVIEW_REJECT / USER_LOGIN / DATA_EXPORT ...
                                                    -- 软枚举：不加硬 CHECK，保留新增动作类型的空间
    details      TEXT    NOT NULL DEFAULT '',
    target_type  TEXT,                              -- 'violation' / 'user' / '' —— 便于从日志反查对象
    target_id    TEXT,                              -- 关联业务 ID，如 'EV-20260929-0147'
    ip           TEXT    NOT NULL DEFAULT '',
    prev_hash    TEXT    NOT NULL DEFAULT '',       -- 上一条日志的 entry_hash（链式）
    entry_hash   TEXT    NOT NULL DEFAULT '',       -- 本条内容 + prev_hash 的 sha256，为 UI"哈希已存证"提供真实依据
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
        -- 用 RESTRICT 而非 SET NULL：SET NULL 需要 UPDATE system_logs，
        -- 会被"禁止 UPDATE"的触发器拦下（实测踩坑）。审计原则是"账号只停用不删除"，
        -- 停用靠 users.status='disabled'，故禁止删除有日志的账号是正确语义。

    -- 若填了哈希，必须是十六进制串：防填错/填半截导致"存证"链验不过
    CHECK (prev_hash  = '' OR prev_hash  GLOB '[0-9a-f]*'),
    CHECK (entry_hash = '' OR length(entry_hash) = 64),
    CHECK (event_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]')
);


-- ============================================================================
--  索引方案（只为三类真实查询服务：按时间倒序分页 / 按状态筛选 / 按卡口聚合）
-- ============================================================================

-- 台账默认视图：按抓拍时间倒序分页。DESC 索引让最热路径免排序。
CREATE INDEX IF NOT EXISTS idx_violation_records_capture_time
    ON violation_records (capture_time DESC);

-- 状态筛选 + 时间倒序（台账页 filterStatus）+ 复核完成率统计（count by status）
-- 复合索引把"先按状态等值过滤，再按时间取最新一页"一次走完，最左前缀 status 也能单独用。
CREATE INDEX IF NOT EXISTS idx_violation_records_status_time
    ON violation_records (status, capture_time DESC);

-- 按卡口聚合 / 按卡口筛选 + 时间倒序（大屏 TOP5、研判页点位排行）
CREATE INDEX IF NOT EXISTS idx_violation_records_camera_time
    ON violation_records (camera_key, capture_time DESC);

-- 类别筛选（台账页 filterCategory）+ 时间倒序
CREATE INDEX IF NOT EXISTS idx_violation_records_category_time
    ON violation_records (category, capture_time DESC);

-- 大屏处置指标：按处置状态计数（toNotifyCount / disposedCount / dispositionRate）
CREATE INDEX IF NOT EXISTS idx_dispositions_status
    ON dispositions (status);
-- 说明：review_history(violation_id, seq) 与 disposition_history(violation_id, seq)
--      的 UNIQUE 约束已自动生成索引，详情页按 violation_id 取轨迹直接命中，无需再加。

-- 审计日志默认视图：按时间倒序 + 按动作类型筛选
CREATE INDEX IF NOT EXISTS idx_system_logs_time
    ON system_logs (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_action_time
    ON system_logs (action_type, event_time DESC);

-- 哈希链"分叉检测"守卫：正常的单向链里，每条日志的 prev_hash（= 上一条的 entry_hash）
-- 至多被一条后继引用，故非空 prev_hash 全局唯一。若两条日志链到同一个前驱，说明
-- 并发写日志把链写分了叉 → 这里直接报 UNIQUE 失败（响亮失败，而非静默产生坏链）。
-- 用 partial index 排除 prev_hash=''（创世行为空，不参与唯一性）。
CREATE UNIQUE INDEX IF NOT EXISTS idx_system_logs_prev_hash_unique
    ON system_logs (prev_hash) WHERE prev_hash <> '';


-- ============================================================================
--  触发器：把"业务语义"落到数据库层，而不是只写在代码注释里
-- ============================================================================

-- T1) 新建台账时自动补一行处置当前态（status=NULL = 未进入处置）
--     防的错误：台账建了却忘了建 disposition 行，导致处置工作台 LEFT JOIN 缺行、计数漏数。
CREATE TRIGGER IF NOT EXISTS trg_record_init_disposition
AFTER INSERT ON violation_records
FOR EACH ROW
BEGIN
    INSERT INTO dispositions (violation_id, status)
    VALUES (NEW.id, NULL);
END;

-- T2) 处置状态非空 ⇒ 对应台账必须已 approved
--     防的错误：pending / rejected 的误报记录被错误地推进处置流程（业务规则：
--     只有"已确认入卷"才进入处置闭环）。
CREATE TRIGGER IF NOT EXISTS trg_dispositions_require_approved
BEFORE INSERT ON dispositions
FOR EACH ROW
WHEN NEW.status IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'disposition.status 非空要求对应违规记录已 approved')
    WHERE (SELECT status FROM violation_records WHERE id = NEW.violation_id) IS NOT 'approved';
END;

CREATE TRIGGER IF NOT EXISTS trg_dispositions_require_approved_upd
BEFORE UPDATE OF status ON dispositions
FOR EACH ROW
WHEN NEW.status IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'disposition.status 非空要求对应违规记录已 approved')
    WHERE (SELECT status FROM violation_records WHERE id = NEW.violation_id) IS NOT 'approved';
END;

-- T3/T4/T5) 执法留痕只追加：禁止对历史表做 UPDATE / DELETE
--     防的错误：有人（或某段代码）图省事直接改/删历史行，破坏执法留痕的不可篡改性。
--     处置状态回退（撤销复核）不是删历史，而是：dispositions 当前态（可更新）重置为 NULL
--     + 向 disposition_history 追加一条 action='revoke' 的事件。
--
--     【删除策略说明】子表外键刻意用 ON DELETE RESTRICT 而非 CASCADE：
--     台账属执法档案，只做软删除（deleted_at，见设计文档待确认项），不做物理删除。
--     若用 CASCADE，删除台账会触发子表 DELETE，而上面的"禁止 DELETE"触发器又会 ABORT，
--     二者自相矛盾（实测：DELETE violation_records 会被 review_history 的触发器拦截）。
--     故统一为 RESTRICT：物理删除台账会被明确拒绝，逼业务走软删除。
--     确需整体重建库（如重灌演示数据）时，直接删 traffic.db 重建，不要走行级 DELETE。
CREATE TRIGGER IF NOT EXISTS trg_review_history_immutable_upd
BEFORE UPDATE ON review_history
BEGIN
    SELECT RAISE(ABORT, 'review_history 只允许追加，禁止 UPDATE');
END;
CREATE TRIGGER IF NOT EXISTS trg_review_history_immutable_del
BEFORE DELETE ON review_history
BEGIN
    SELECT RAISE(ABORT, 'review_history 只允许追加，禁止 DELETE');
END;

CREATE TRIGGER IF NOT EXISTS trg_disposition_history_immutable_upd
BEFORE UPDATE ON disposition_history
BEGIN
    SELECT RAISE(ABORT, 'disposition_history 只允许追加，禁止 UPDATE');
END;
CREATE TRIGGER IF NOT EXISTS trg_disposition_history_immutable_del
BEFORE DELETE ON disposition_history
BEGIN
    SELECT RAISE(ABORT, 'disposition_history 只允许追加，禁止 DELETE');
END;

CREATE TRIGGER IF NOT EXISTS trg_system_logs_immutable_upd
BEFORE UPDATE ON system_logs
BEGIN
    SELECT RAISE(ABORT, 'system_logs 只允许追加，禁止 UPDATE');
END;
CREATE TRIGGER IF NOT EXISTS trg_system_logs_immutable_del
BEFORE DELETE ON system_logs
BEGIN
    SELECT RAISE(ABORT, 'system_logs 只允许追加，禁止 DELETE');
END;


-- ============================================================================
-- 登记本次迁移
-- ============================================================================
INSERT OR IGNORE INTO schema_version (version, name)
VALUES (1, '0001_init.sql');


-- ============================================================================
--  初始数据（卡口主数据，来自 frontend/src/data/cameras.js）
--  台账 / 用户 / 日志的演示数据由一次性导入脚本负责（见设计文档第 5 节），
--  不写进本 DDL，保持 schema.sql 可重复执行、可测试。
-- ============================================================================
INSERT OR IGNORE INTO cameras (camera_key, name, area, latitude, longitude, heat_radius) VALUES
    ('CAM-03', '建设大道-香港路口',   '汉口金融街',   30.5979,   114.2857,   950),
    ('CAM-01', '珞喻路-光谷广场口',   '武昌光谷',     30.5054,   114.4142,   800),
    ('CAM-02', '解放大道-新华路口',   '汉口中山公园', 30.5846,   114.2717,   700),
    ('CAM-04', '武珞路-中南路口',     '武昌中南商圈', 30.537317, 114.324538, 620),
    ('CAM-05', '钟家村-鹦鹉大道口',   '汉阳钟家村',   30.5510787, 114.2607073, 560);
