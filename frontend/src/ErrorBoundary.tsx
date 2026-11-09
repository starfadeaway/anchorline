import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button, Result } from "antd";

type Props = { children: ReactNode };
type State = { error: Error | null };

/**
 * 全局错误边界：任何页面组件渲染抛错时显示降级页，而不是白屏崩溃。
 * 只捕获渲染期错误；事件处理/异步错误由 window.onerror + message 兜底。
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 不把堆栈渲染到页面，只记录到控制台，避免暴露内部信息
    console.error("[anchorline] UI crash:", error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (error) {
      return (
        <Result
          status="error"
          title="页面出错了"
          subTitle={error.message || "未知渲染错误，可重试或刷新页面"}
          extra={[
            <Button type="primary" key="retry" onClick={() => this.setState({ error: null })}>
              重试
            </Button>,
            <Button key="reload" onClick={() => window.location.reload()}>
              刷新页面
            </Button>,
          ]}
        />
      );
    }
    return this.props.children;
  }
}
