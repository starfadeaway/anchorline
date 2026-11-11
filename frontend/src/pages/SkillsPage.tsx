import { useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, Modal, Space, Switch, Table, Tag, Typography, message } from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { api, type SkillInfo } from "../api";

const { Paragraph, Text } = Typography;

/** 通用模板：用户可基于它改出任意技能（name 建后不可改，内容可编辑）。 */
const TEMPLATE = `# 通用技能模板（把下面内容改成你的技能；保存后开启即生效）
# name 只能是 2-33 位小写字母/数字/下划线，且以字母开头；name 建后不可改
#
# 示例：
# name: travel_plan
# title: 旅行规划
# description: 按记忆里的旅行计划给行程建议
# instructions: 用户问旅行/行程时，先检索记忆里的目的地、天数、预算；给出按天行程；不要编造未记录的偏好。`;

type EditState = { mode: "create" | "edit"; name?: string } | null;

/** 技能页：内置 + 自定义技能，可开关、可新建/编辑/删除（自定义）。 */
export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [error, setError] = useState("");
  const [edit, setEdit] = useState<EditState>(null);
  const [form] = Form.useForm();

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
    form.setFieldsValue({ name: "", title: "", description: "", instructions: TEMPLATE });
    setEdit({ mode: "create" });
  };

  const openEdit = (sk: SkillInfo) => {
    form.setFieldsValue({ name: sk.name, title: sk.title, description: sk.description, instructions: "" });
    setEdit({ mode: "edit", name: sk.name });
  };

  const submit = async () => {
    const v = await form.validateFields();
    try {
      if (edit?.mode === "create") {
        await api.createSkill({ name: v.name.trim(), title: v.title.trim(), description: v.description?.trim() ?? "", instructions: v.instructions.trim() });
        message.success("技能已创建并默认开启");
      } else if (edit?.mode === "edit" && edit.name) {
        await api.updateSkill(edit.name, { title: v.title.trim(), description: v.description?.trim() ?? "", instructions: v.instructions.trim() });
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
      <Paragraph type="secondary">
        技能是提示模块：开启后聊天时把技能指令拼进 system prompt（不引入外部工具、不越过记忆边界）。
        内置技能只能开关；自定义技能可编辑/删除。
      </Paragraph>
      {error && <Alert type="error" showIcon message="技能加载失败" description={error} style={{ marginBottom: 12 }} />}
      <Table rowKey="name" size="small" dataSource={skills} columns={columns} pagination={false} />

      <Modal
        open={edit !== null}
        title={edit?.mode === "create" ? "新建技能" : `编辑技能：${edit?.name ?? ""}`}
        okText="保存"
        onOk={() => void submit()}
        onCancel={() => setEdit(null)}
        width={720}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="标识（name）"
            rules={[
              { required: edit?.mode === "create", message: "创建时必须填 name" },
              { pattern: /^[a-z][a-z0-9_]{1,32}$/, message: "2-33 位小写字母/数字/下划线，以字母开头" },
            ]}
          >
            <Input placeholder="如 travel_plan" disabled={edit?.mode === "edit"} />
          </Form.Item>
          <Form.Item name="title" label="标题" rules={[{ required: true, message: "填标题" }]}>
            <Input placeholder="如 旅行规划" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="一句话说明这个技能做什么（列表里展示）" />
          </Form.Item>
          <Form.Item name="instructions" label="指令（注入 system prompt）" rules={[{ required: true, message: "指令不能为空" }]}>
            <Input.TextArea rows={10} placeholder="基于上方通用模板填写；越具体越好（什么时候用、先做什么、不要做什么）" />
          </Form.Item>
        </Form>
        <Paragraph type="secondary" style={{ marginBottom: 0, fontSize: 12 }}>
          模板提示：name 建后不可改；内置技能不能删除，只能关闭；自定义技能默认开启。
        </Paragraph>
      </Modal>
    </Card>
  );
}
