import { useEffect, useState } from "react";
import { Card, Table, Tag, Typography, message } from "antd";
import { api, type EvalArm } from "../api";

const { Paragraph, Text } = Typography;

/** 评测页：展示已跑出的臂级结果（读后端 /eval/summary）。 */
export default function EvalPage() {
  const [rows, setRows] = useState<EvalArm[]>([]);

  useEffect(() => {
    api.evalSummary().then(setRows).catch((e) => message.error(String(e)));
  }, []);

  const columns = [
    { title: "臂", dataIndex: "arm", width: 220 },
    {
      title: "准确率",
      dataIndex: "accuracy",
      width: 120,
      render: (v: number) => <Text strong>{(v * 100).toFixed(1)}%</Text>,
    },
    { title: "题数", dataIndex: "n", width: 90 },
    { title: "来源", dataIndex: "source", width: 240 },
    { title: "备注", dataIndex: "note", render: (v?: string) => v ?? "—" },
  ];

  return (
    <Card title="评测结果">
      <Paragraph type="secondary">
        口径：同 reader / 同 embedding / 同判分 / 同 4k 预算下的相对结果；不进官方 leaderboard。
        154 题为确定性判分；168 题为 154 + 14 道 LLM judge（judge prompt 已冻结）。
      </Paragraph>
      <Table rowKey={(r) => `${r.arm}-${r.source}`} size="small" dataSource={rows} columns={columns} pagination={false} />
      <div style={{ marginTop: 12 }}>
        <Tag color="blue">A/A 噪声底</Tag>
        <Text type="secondary">配对 |Δ| 均值 6.3pp（20 题 × 10 次），差异需超过噪声底才可称提升。</Text>
      </div>
    </Card>
  );
}
