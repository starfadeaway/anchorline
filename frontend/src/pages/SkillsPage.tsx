import { useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, Modal, Select, Space, Switch, Table, Tag, Typography, message } from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { api, type SkillInfo } from "../api";

const { Paragraph, Text } = Typography;

type Template = { label: string; name: string; title: string; description: string; instructions: string; memory_entity?: string };

/** 预置模板：用户可直接选用，也可以基于通用模板自己写，或让系统按描述生成。 */
const TEMPLATES: Template[] = [
  {
    label: "跑步教练",
    name: "run_coach",
    title: "跑步教练",
    description: "按记忆里的 PB / 目标 / 伤病史给训练建议",
    instructions: "用户问跑步、配速、训练计划时：先检索记忆中的 PB、目标、伤病史；给出可执行的周计划（跑量/配速区间/休息日）；不要编造未记录的成绩。",
  },
  {
    label: "饮食规划",
    name: "diet_plan",
    title: "饮食规划",
    description: "按饮食偏好 / 禁忌给配餐建议",
    instructions: "用户问吃什么、配餐时：先检索记忆里的饮食偏好与禁忌；优先蒸煮/凉拌；避开明确禁忌；不确定时先问。",
  },
  {
    label: "知识库问答",
    name: "kb_search",
    title: "知识库问答",
    description: "用 kb_search 检索 LoreKeeper 三库 wiki",
    instructions: "用户问原神/星铁/绝区零 wiki 内容时，用 kb_search 检索；回答时引用页面标题；不要用事实记忆替代 wiki 复述。",
  },
  {
    label: "旅行规划",
    name: "travel_plan",
    title: "旅行规划",
    description: "按记忆里的旅行计划给行程建议",
    instructions: "用户问旅行/行程时：先检索记忆里的目的地、天数、预算；给出按天行程；不要编造未记录的偏好。",
    memory_entity: "user",
  },
  {
    label: "写作润色",
    name: "writing_polish",
    title: "写作润色",
    description: "帮用户润色文字，保持原意",
    instructions: "用户要求润色/改写文字时：保持原意和事实不变，只调整表达与结构；指出修改点；不要加入未提供的新信息。",
  },
  {
    label: "英文翻译",
    name: "translate_en",
    title: "英文翻译",
    description: "中文 ↔ 英文互译",
    instructions: "用户要求翻译时：中英互译，保留专有名词；给出译文后附一句术语说明（如有）；不要意译成改变原意的版本。",
  },
  {
    label: "面试复盘",
    name: "interview_review",
    title: "面试复盘",
    description: "根据用户的面试记录做复盘",
    instructions: "用户做面试复盘时：先检索记忆里的项目经历与目标岗位；按「问题-回答-改进」组织；不要编造用户没做过的项目。",
  },
];

const TEMPLATE_HINT = `模板提示：
- name 只能是 2-33 位小写字母/数字/下划线（建后不可改）
- instructions 是注入 system prompt 的指令：写清楚「什么时候用 / 先检索什么 / 怎么回答 / 不要做什么」
- 内置技能不能删除，只能关闭；自定义技能默认开启；保存后立即生效`;

type EditState = { mode: "create" | "edit"; name?: string } | null;

/** 技能页：内置 + 自定义技能；支持模板填充、按描述自动生成、开关/编辑/删除。 */
export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [error, setError] = useState("");
  const [edit, setEdit] = useState<EditState>(null);
  const [form] = Form.useForm();
  const [genDesc, setGenDesc] = useState("");
  const [genBusy, setGenBusy] = useState(false);

  const load = () =>
    api
      .listSkills()
      .then((rows) => {
        setSkills(rows);
        setError("");
      })
      .catch((e) => setError(String(e)));

  useEffect(() => {
    void load();
  }, []);

  const openCreate = () => {
    form.setFieldsValue({ name: "", title: "", description: "", instructions: "", memory_entity: "", auto_activate: false, trigger_keywords: "" });
    setGenDesc("");
    setEdit({ mode: "create" });
  };

  const openEdit = (sk: SkillInfo) => {
    form.setFieldsValue({
      name: sk.name,
      title: sk.title,
      description: sk.description,
      instructions: "",
      memory_entity: sk.memory_entity ?? "",
      auto_activate: sk.auto_activate ?? false,
      trigger_keywords: sk.trigger_keywords ?? "",
    });
    setGenDesc("");
    setEdit({ mode: "edit", name: sk.name });
  };

  const applyTemplate = (label: string) => {
    const t = TEMPLATES.find((x) => x.label === label);
    if (!t) return;
    form.setFieldsValue({
      name: t.name,
      title: t.title,
      description: t.description,
      instructions: t.instructions,
      memory_entity: t.memory_entity ?? "",
    });
    message.success(`已填入模板「${t.label}」，可继续修改`);
  };

  const generate = async () => {
    if (!genDesc.trim()) {
      message.warning("先描述一下这个技能要做什么");
      return;
    }
    setGenBusy(true);
    try {
      const d = await api.generateSkill(genDesc.trim());
      form.setFieldsValue({ name: d.name, title: d.title, description: d.description, instructions: d.instructions });
      message.success("已生成草稿，请检查后保存");
    } catch (e) {
      message.error(`自动生成失败：${String(e)}（可以手写或选模板）`);
    } finally {
      setGenBusy(false);
    }
  };

  const submit = async () => {
    const v = await form.validateFields();
    try {
      if (edit?.mode === "create") {
        await api.createSkill({
          name: v.name.trim(),
          title: v.title.trim(),
          description: v.description?.trim() ?? "",
          instructions: v.instructions.trim(),
          memory_entity: (v.memory_entity ?? "").trim(),
          auto_activate: !!v.auto_activate,
          trigger_keywords: (v.trigger_keywords ?? "").trim(),
        });
        message.success("技能已创建并默认开启");
      } else if (edit?.mode === "edit" && edit.name) {
        await api.updateSkill(edit.name, {
          title: v.title.trim(),
          description: v.description?.trim() ?? "",
          instructions: v.instructions.trim(),
          memory_entity: (v.memory_entity ?? "").trim(),
          auto_activate: !!v.auto_activate,
          trigger_keywords: (v.trigger_keywords ?? "").trim(),
        });
        message.success("技能已更新");
      }
      setEdit(null);
      void load();
    } catch (e) {
      message.error(`保存失败：${String(e)}`);
    }
  };

  const columns = [
    { title: "技能", dataIndex: "title", width: 140 },
    { title: "标识", dataIndex: "name", width: 150, render: (v: string) => <Text code>{v}</Text> },
    {
      title: "来源",
      dataIndex: "source",
      width: 90,
      render: (v: string) => <Tag color={v === "custom" ? "purple" : "blue"}>{v === "custom" ? "自定义" : "内置"}</Tag>,
    },
    { title: "描述", dataIndex: "description", ellipsis: true },
    {
      title: "关联记忆",
      dataIndex: "memory_entity",
      width: 170,
      render: (_: unknown, r: SkillInfo) =>
        r.memory_entity ? (
          <Link
            to={`/memory?entity=${encodeURIComponent(r.memory_entity)}`}
            title={`跳转到记忆页过滤 ${r.memory_entity}（注入时会附上其当前事实）`}
          >
            <Text code>
              {r.memory_entity}（{r.memory_fact_count ?? 0} 条）
            </Text>
          </Link>
        ) : (
          <Text type="secondary">未绑定</Text>
        ),
    },
    {
      title: "自动",
      dataIndex: "auto_activate",
      width: 70,
      render: (v: boolean, r: SkillInfo) =>
        v ? <Tag color="gold" title={`关键词命中时自动启用：${r.trigger_keywords ?? ""}`}>自动</Tag> : <Text type="secondary">—</Text>,
    },
    {
      title: "开关",
      dataIndex: "enabled",
      width: 80,
      render: (v: boolean, r: SkillInfo) => (
        <Switch
          checked={v}
          onChange={(on) =>
            api
              .updateSkill(r.name, { enabled: on })
              .then(() => setSkills((prev) => prev.map((x) => (x.name === r.name ? { ...x, enabled: on } : x))))
              .catch((e) => message.error(`切换失败：${String(e)}`))
          }
        />
      ),
    },
    {
      title: "操作",
      width: 140,
      render: (_: unknown, r: SkillInfo) =>
        r.source === "custom" ? (
          <Space size={6}>
            <Button size="small" icon={<EditOutlined />} title="编辑内容" onClick={() => openEdit(r)} />
            <Button
              size="small"
              danger
              type="text"
              icon={<DeleteOutlined />}
              title="删除自定义技能"
              onClick={() =>
                Modal.confirm({
                  title: `删除技能「${r.title}」？`,
                  content: "删除后聊天不再注入该技能；内置技能只能关闭不能删除。",
                  okText: "删除",
                  okButtonProps: { danger: true },
                  onOk: async () => {
                    await api.deleteSkill(r.name);
                    message.success("已删除");
                    void load();
                  },
                })
              }
            />
          </Space>
        ) : (
          <Text type="secondary">内置（只能开关）</Text>
        ),
    },
  ];

  return (
    <Card
      title="技能（可开关）"
      extra={
        <Space>
          <Button onClick={() => void load()}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建技能
          </Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="技能是什么、怎么写"
        description={
          <div style={{ lineHeight: 1.8 }}>
            <div>· 技能 = <b>提示模块</b>：开启后聊天时把技能指令拼进 system prompt（不引入外部工具、不越过记忆边界）。</div>
            <div>· 三种做法：<b>选一个模板</b>快速改 → <b>描述功能让系统自动生成草稿</b> → 或手写 instructions。</div>
            <div>· instructions 建议写清四件事：什么时候用 / 先检索记忆里的什么 / 怎么组织回答 / 不要做什么。</div>
            <div>· <b>关联记忆（可选）</b>：绑定一个实体（如 user）后，该实体的当前事实会自动附在技能指令后面一起注入——技能就能直接用到你的 PB、偏好等记忆。</div>
          </div>
        }
      />
      {error && <Alert type="error" showIcon message="技能加载失败" description={error} style={{ marginBottom: 12 }} />}
      <Table rowKey="name" size="small" dataSource={skills} columns={columns} pagination={false} />

      <Modal
        open={edit !== null}
        title={edit?.mode === "create" ? "新建技能" : `编辑技能：${edit?.name ?? ""}`}
        okText="保存"
        onOk={() => void submit()}
        onCancel={() => setEdit(null)}
        width={780}
      >
        {edit?.mode === "create" && (
          <>
            <Paragraph type="secondary" style={{ marginBottom: 6 }}>
              <b>方式一：选预置模板</b>（自动填入下方表单，可继续改）
            </Paragraph>
            <Space style={{ marginBottom: 10 }}>
              <Select
                placeholder="选择模板…"
                style={{ width: 240 }}
                options={TEMPLATES.map((x) => ({ label: x.label, value: x.label }))}
                onChange={(v) => applyTemplate(String(v))}
              />
            </Space>
            <Paragraph type="secondary" style={{ marginBottom: 6, marginTop: 4 }}>
              <b>方式二：描述功能，自动生成草稿</b>（调用 reader 模型生成 system prompt）
            </Paragraph>
            <Space.Compact style={{ width: "100%", marginBottom: 10 }}>
              <Input.TextArea
                rows={2}
                value={genDesc}
                onChange={(e) => setGenDesc(e.target.value)}
                placeholder="例：用户问旅行计划时，先查记忆里的目的地和天数，按天给行程，不要编造偏好"
              />
              <Button type="primary" icon={<ThunderboltOutlined />} loading={genBusy} onClick={() => void generate()}>
                自动生成
              </Button>
            </Space.Compact>
            <Paragraph type="secondary" style={{ marginBottom: 6 }}>
              <b>方式三：直接手写</b>（下方表单）
            </Paragraph>
          </>
        )}
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="标识（name）"
            rules={[
              { required: edit?.mode === "create", message: "创建时必须填 name" },
              { pattern: /^[a-z][a-z0-9_]{1,32}$/, message: "2-33 位小写字母/数字/下划线，以字母开头" },
            ]}
          >
            <Input placeholder="如 travel_plan（建后不可改）" disabled={edit?.mode === "edit"} />
          </Form.Item>
          <Form.Item name="title" label="标题" rules={[{ required: true, message: "填标题" }]}>
            <Input placeholder="如 旅行规划" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="一句话说明这个技能做什么（列表里展示）" />
          </Form.Item>
          <Form.Item
            name="memory_entity"
            label="关联记忆实体（可选）"
            extra="绑定的实体当前事实会自动附在技能指令后（如 user / user.猫）；留空则不绑定"
          >
            <Input placeholder="如 user" />
          </Form.Item>
          <Form.Item
            name="auto_activate"
            label="主题命中时自动启用"
            valuePropName="checked"
            extra="开启后：用户问题包含任一触发关键词时自动注入本技能（不依赖上面的手动开关）"
          >
            <Switch checkedChildren="自动" unCheckedChildren="手动" />
          </Form.Item>
          <Form.Item name="trigger_keywords" label="触发关键词">
            <Input placeholder="逗号分隔，如 原神,星铁,wiki" />
          </Form.Item>
          <Form.Item
            name="instructions"
            label="指令（注入 system prompt）"
            rules={[{ required: true, message: "指令不能为空" }]}
            extra={TEMPLATE_HINT}
          >
            <Input.TextArea rows={9} placeholder="写清楚：什么时候用、先检索什么、怎么回答、不要做什么" />
          </Form.Item>
        </Form>
        <Paragraph type="secondary" style={{ marginBottom: 0, fontSize: 12 }}>
          自动生成会调用一次 reader 模型（约几秒）；结果只是草稿，保存前请检查是否编造了未记录的信息。
        </Paragraph>
      </Modal>
    </Card>
  );
}
