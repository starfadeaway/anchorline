import { useEffect, useMemo, useRef, useState } from "react";
import { Card, Empty, Progress, Space, Table, Tag, Typography, message } from "antd";
import { api, type EvalArm } from "../api";

const { Paragraph, Text } = Typography;

/** 数字增长动画（ease-out）。 */
function useCountUp(target: number, ms = 700): number {
  const [value, setValue] = useState(0);
  const raf = useRef(0);
  useEffect(() => {
    const t0 = performance.now();
    const step = (t: number) => {
      const p = Math.min(1, (t - t0) / ms);
      setValue(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [target, ms]);
  return value;
}

function ArmRow({ arm }: { arm: EvalArm }) {
  const pct = useCountUp(arm.accuracy * 100);
  return (
    <div style={{ marginBottom: 14 }}>
      <Space split="·" size={8} style={{ marginBottom: 4 }}>
        <Text strong>{arm.arm}</Text>
        <Tag>{(pct / 100).toFixed(1)}%</Tag>
        <Text type="secondary" style={{ fontSize: 11 }}>{arm.n} 题</Text>
      </Space>
      <Progress
        percent={pct}
        showInfo={false}
        strokeColor={{ "0%": "#00d4ff", "100%": "#7c5cff" }}
        trailColor="rgba(255,255,255,0.06)"
        strokeLinecap="round"
      />
    </div>
  );
}

/** 实验对比：臂准确率横向条形（生长动画 + 数字增长）+ 表格。 */
export default function ComparePage() {
  const [rows, setRows] = useState<EvalArm[]>([]);

  useEffect(() => {
    api.evalSummary().then(setRows).catch((e) => message.error(String(e)));
  }, []);

  const maxAcc = useMemo(() => Math.max(...rows.map((r) => r.accuracy), 0.01), [rows]);

  const columns = [
    { title: "臂", dataIndex: "arm", width: 260 },
    { title: "准确率", dataIndex: "accuracy", width: 100, render: (v: number) => <Text strong>{(v * 100).toFixed(1)}%</Text> },
    { title: "题数", dataIndex: "n", width: 80 },
    { title: "来源", dataIndex: "source", width: 220 },
    { title: "备注", dataIndex: "note", render: (v?: string) => v ?? "—" },
  ];

  return (
    <Card title="实验对比">
      <Paragraph type="secondary">
        同 reader / embedding / 判分 / 预算下的相对结果；条长按最高准确率归一（{maxAcc.toFixed(4)} = 100%）。A/A 噪声底：配对 |Δ| 均值 6.3pp。
      </Paragraph>
      {rows.length === 0 ? (
        <Empty description="暂无评测结果" />
      ) : (
        <>
          {rows.map((r) => <ArmRow key={`${r.arm}-${r.source}`} arm={r} />)}
          <Table rowKey={(r) => `${r.arm}-${r.source}`} size="small" dataSource={rows} columns={columns} pagination={false} style={{ marginTop: 12 }} />
        </>
      )}
    </Card>
  );
}
