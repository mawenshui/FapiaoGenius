"""发票统计报表页面"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QScrollArea, QGroupBox, QGridLayout)
from PyQt5.QtCore import Qt
from core.logger import logger


class StatsPage(QWidget):
    """发票统计报表页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("📊 统计报表")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新数据")
        refresh_btn.clicked.connect(self.refresh)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff; color: white;
                padding: 8px 16px; border-radius: 4px; border: none;
            }
            QPushButton:hover { background-color: #40a9ff; }
        """)
        title_layout.addWidget(refresh_btn)
        layout.addLayout(title_layout)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setSpacing(15)
        
        # 总览卡片
        self._summary_group = QGroupBox("数据总览")
        self._summary_layout = QGridLayout(self._summary_group)
        self._summary_layout.setSpacing(15)
        self._content_layout.addWidget(self._summary_group)
        
        # 图表区域
        self._charts_group = QGroupBox("图表分析")
        self._charts_layout = QVBoxLayout(self._charts_group)
        self._charts_layout.setSpacing(10)
        self._content_layout.addWidget(self._charts_group)
        
        self._content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # 图表画布引用
        self._canvas_widgets = []
    
    def refresh(self):
        """刷新统计数据"""
        from services.stats_service import stats_service
        
        # 获取总览
        summary = stats_service.summary()
        self._update_summary(summary)
        
        # 获取分类数据
        by_business = stats_service.by_business_type()
        by_month = stats_service.by_month()
        by_reimbursement = stats_service.by_reimbursement_status()
        
        # 更新图表
        self._update_charts(by_business, by_month, by_reimbursement)
        
        logger.info("统计报表已刷新")
    
    def _update_summary(self, summary: dict):
        """更新总览卡片"""
        # 清除旧内容
        while self._summary_layout.count():
            item = self._summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        cards = [
            ("发票总数", f"{summary['total_count']}", "张"),
            ("总金额", f"¥{summary['total_amount']:,.2f}", ""),
            ("总税额", f"¥{summary['total_tax']:,.2f}", ""),
            ("平均金额", f"¥{summary['avg_amount']:,.2f}", ""),
            ("最大金额", f"¥{summary['max_amount']:,.2f}", ""),
            ("最小金额", f"¥{summary['min_amount']:,.2f}", ""),
        ]
        
        for col, (label, value, unit) in enumerate(cards):
            card = self._create_summary_card(label, value, unit)
            self._summary_layout.addWidget(card, 0, col)
    
    def _create_summary_card(self, label: str, value: str, unit: str) -> QWidget:
        """创建总览卡片"""
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #f6f8fa;
                border: 1px solid #e8e8e8;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        card.setMinimumWidth(120)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标签
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(lbl)
        
        # 值
        val = QLabel(f"{value}{unit}")
        val.setStyleSheet("font-size: 18px; font-weight: bold; color: #1890ff;")
        val.setAlignment(Qt.AlignCenter)
        layout.addWidget(val)
        
        return card
    
    def _update_charts(self, by_business, by_month, by_reimbursement):
        """更新图表"""
        # 清除旧图表
        for widget in self._canvas_widgets:
            widget.deleteLater()
        self._canvas_widgets.clear()
        
        while self._charts_layout.count():
            item = self._charts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        try:
            import matplotlib
            matplotlib.use('Agg')  # 使用非交互后端
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            
            # 设置中文字体
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 图表1: 业务类型分布（饼图+柱状图）
            if by_business:
                fig1 = Figure(figsize=(8, 3.5), dpi=100)
                ax1 = fig1.add_subplot(121)
                ax2 = fig1.add_subplot(122)
                
                labels = [item.label for item in by_business[:8]]
                amounts = [item.total_amount for item in by_business[:8]]
                counts = [item.count for item in by_business[:8]]
                
                # 饼图 - 金额占比
                if sum(amounts) > 0:
                    ax1.pie(amounts, labels=labels, autopct='%1.1f%%', 
                           startangle=90, textprops={'fontsize': 9})
                    ax1.set_title('金额占比', fontsize=11, fontweight='bold')
                
                # 柱状图 - 张数
                ax2.barh(labels, counts, color='#1890ff', alpha=0.8)
                ax2.set_title('发票张数', fontsize=11, fontweight='bold')
                ax2.set_xlabel('张数')
                
                fig1.tight_layout()
                canvas1 = FigureCanvas(fig1)
                canvas1.setMinimumHeight(280)
                self._charts_layout.addWidget(canvas1)
                self._canvas_widgets.append(canvas1)
            
            # 图表2: 月份趋势（折线图）
            if by_month:
                fig2 = Figure(figsize=(8, 3), dpi=100)
                ax = fig2.add_subplot(111)
                
                months = [item.label for item in by_month]
                amounts = [item.total_amount for item in by_month]
                
                ax.plot(months, amounts, marker='o', color='#1890ff', linewidth=2, markersize=6)
                ax.fill_between(range(len(months)), amounts, alpha=0.1, color='#1890ff')
                ax.set_title('月度金额趋势', fontsize=11, fontweight='bold')
                ax.set_ylabel('金额 (元)')
                ax.grid(True, alpha=0.3)
                
                # 旋转x轴标签
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
                fig2.tight_layout()
                
                canvas2 = FigureCanvas(fig2)
                canvas2.setMinimumHeight(250)
                self._charts_layout.addWidget(canvas2)
                self._canvas_widgets.append(canvas2)
            
            # 图表3: 报销状态分布（环形图）
            if by_reimbursement:
                fig3 = Figure(figsize=(5, 3), dpi=100)
                ax = fig3.add_subplot(111)
                
                labels = [item.label for item in by_reimbursement]
                counts = [item.count for item in by_reimbursement]
                colors = ['#52c41a', '#faad14', '#f5222d']  # 绿/黄/红
                
                wedges, texts, autotexts = ax.pie(
                    counts, labels=labels, autopct='%1.0f%%',
                    colors=colors[:len(labels)], pctdistance=0.75,
                    startangle=90, textprops={'fontsize': 10}
                )
                # 环形效果
                centre_circle = plt.Circle((0, 0), 0.50, fc='white')
                ax.add_artist(centre_circle)
                ax.set_title('报销状态分布', fontsize=11, fontweight='bold')
                
                fig3.tight_layout()
                canvas3 = FigureCanvas(fig3)
                canvas3.setMinimumHeight(250)
                self._charts_layout.addWidget(canvas3)
                self._canvas_widgets.append(canvas3)
                
        except ImportError:
            no_chart = QLabel("⚠ matplotlib 未安装，无法显示图表\n请执行: pip install matplotlib")
            no_chart.setAlignment(Qt.AlignCenter)
            no_chart.setStyleSheet("color: #faad14; font-size: 14px; padding: 30px;")
            self._charts_layout.addWidget(no_chart)
            logger.warning("matplotlib 未安装，图表功能不可用")
        except Exception as e:
            error_label = QLabel(f"图表渲染失败: {e}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: #f5222d; padding: 20px;")
            self._charts_layout.addWidget(error_label)
            logger.error(f"图表渲染失败: {e}")
