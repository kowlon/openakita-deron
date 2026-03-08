import { ReactNode } from 'react'

type ThreeColumnLayoutProps = {
  leftSidebar: ReactNode
  mainContent: ReactNode
  detailPanel: ReactNode | null
}

export function ThreeColumnLayout({ leftSidebar, mainContent, detailPanel }: ThreeColumnLayoutProps) {
  return (
    <div className="flex h-full w-full bg-background-dark">
      {/* 左侧边栏 - 256px，小屏幕隐藏 */}
      <aside className="hidden md:flex w-64 h-full shrink-0">
        {leftSidebar}
      </aside>

      {/* 中间主区域 - 自适应宽度 */}
      <main className="flex-1 h-full min-w-0">
        {mainContent}
      </main>

      {/* 右侧详情面板 - 450px，中等屏幕隐藏，大屏幕显示 */}
      {detailPanel && (
        <aside className="hidden xl:flex w-[450px] h-full shrink-0">
          {detailPanel}
        </aside>
      )}
    </div>
  )
}

export default ThreeColumnLayout
