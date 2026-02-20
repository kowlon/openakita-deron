import { ReactNode } from 'react'

type ThreeColumnLayoutProps = {
  leftSidebar: ReactNode
  mainContent: ReactNode
  detailPanel: ReactNode | null
}

export function ThreeColumnLayout({ leftSidebar, mainContent, detailPanel }: ThreeColumnLayoutProps) {
  return (
    <div className="flex h-full w-full bg-background-dark">
      {/* 左侧边栏 - 固定宽度 288px */}
      <aside className="w-72 h-full shrink-0">
        {leftSidebar}
      </aside>

      {/* 中间主区域 - 自适应宽度 */}
      <main className="flex-1 h-full min-w-0">
        {mainContent}
      </main>

      {/* 右侧详情面板 - 固定宽度 384px，条件渲染 */}
      {detailPanel && (
        <aside className="w-96 h-full shrink-0">
          {detailPanel}
        </aside>
      )}
    </div>
  )
}

export default ThreeColumnLayout
