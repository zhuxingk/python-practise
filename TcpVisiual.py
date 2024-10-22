import sys
import logging
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QGraphicsView, QGraphicsScene, QLabel, QMessageBox
from PyQt5.QtGui import QPen, QColor, QBrush, QFont
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtNetwork import QTcpServer, QTcpSocket, QHostAddress, QAbstractSocket

class TCPVisualization(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.initNetwork()
        self.initLogging()

    def initUI(self):
        self.setWindowTitle('TCP连接可视化')
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        layout.addWidget(self.view)

        handshake_button = QPushButton('展示三次握手')
        handshake_button.clicked.connect(self.show_handshake)
        layout.addWidget(handshake_button)

        teardown_button = QPushButton('展示连接断开')
        teardown_button.clicked.connect(self.show_teardown)
        layout.addWidget(teardown_button)

        self.scene.setSceneRect(0, 0, 700, 500)
        self.draw_hosts()

        self.status_label = QLabel("状态: 未连接")
        layout.addWidget(self.status_label)

    def initNetwork(self):
        # 创建服务器
        self.server = QTcpServer(self)
        if not self.server.listen(QHostAddress.LocalHost, 12345):
            QMessageBox.critical(self, "服务器错误", f"无法启动服务器: {self.server.errorString()}")
            self.close()
            return

        self.server.newConnection.connect(self.on_new_connection)

        # 创建客户端套接字
        self.client_socket = QTcpSocket(self)
        self.client_socket.connected.connect(self.on_client_connected)
        self.client_socket.disconnected.connect(self.on_client_disconnected)
        self.client_socket.error.connect(self.on_socket_error)

        # 添加连接超时
        self.connection_timer = QTimer(self)
        self.connection_timer.setSingleShot(True)
        self.connection_timer.timeout.connect(self.on_connection_timeout)

    def initLogging(self):
        logging.basicConfig(filename='tcp_visualization.log', level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(message)s')

    def draw_hosts(self):
        self.scene.clear()
        self.scene.addRect(50, 50, 100, 400, QPen(Qt.black), QBrush(Qt.lightGray))
        self.scene.addRect(550, 50, 100, 400, QPen(Qt.black), QBrush(Qt.lightGray))
        self.scene.addText("客户端").setPos(75, 20)
        self.scene.addText("服务器").setPos(575, 20)

    def draw_arrow(self, start, end, color, text):
        line = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), QPen(color, 2))
        angle = line.line().angle()
        arrow_p1 = line.line().p2() - QPointF(15 * 1.73, 15)
        arrow_p2 = line.line().p2() - QPointF(15 * 1.73, -15)
        self.scene.addLine(line.line().p2().x(), line.line().p2().y(), arrow_p1.x(), arrow_p1.y(), QPen(color, 2))
        self.scene.addLine(line.line().p2().x(), line.line().p2().y(), arrow_p2.x(), arrow_p2.y(), QPen(color, 2))
        text_item = self.scene.addText(text)
        text_item.setPos((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
        text_item.setFont(QFont("Arial", 10))
        text_item.setDefaultTextColor(color)

    def show_handshake(self):
        self.draw_hosts()
        self.status_label.setText("状态: 开始连接")
        try:
            # 客户端尝试连接到服务器
            self.client_socket.connectToHost(QHostAddress.LocalHost, 12345)
            # 设置5秒连接超时
            self.connection_timer.start(5000)
        except Exception as e:
            self.handle_error("连接错误", str(e))

    def on_new_connection(self):
        try:
            # 服务器接受连接
            self.server_socket = self.server.nextPendingConnection()
            self.server_socket.readyRead.connect(self.on_server_ready_read)
            self.server_socket.error.connect(self.on_socket_error)
            self.draw_arrow(QPointF(150, 100), QPointF(550, 200), Qt.blue, "SYN")
            self.status_label.setText("状态: 服务器接受连接")
        except Exception as e:
            self.handle_error("新连接错误", str(e))

    def on_client_connected(self):
        self.connection_timer.stop()  # 停止连接超时计时器
        try:
            # 客户端连接成功
            self.draw_arrow(QPointF(550, 200), QPointF(150, 300), Qt.green, "SYN+ACK")
            self.client_socket.write(b"ACK")
            self.draw_arrow(QPointF(150, 300), QPointF(550, 400), Qt.red, "ACK")
            self.status_label.setText("状态: 连接建立")
        except Exception as e:
            self.handle_error("客户端连接错误", str(e))

    def on_server_ready_read(self):
        try:
            # 服务器接收到ACK
            data = self.server_socket.readAll()
            if data == b"ACK":
                self.status_label.setText("状态: 三次握手完成")
        except Exception as e:
            self.handle_error("服务器读取错误", str(e))

    def show_teardown(self):
        if hasattr(self, 'client_socket') and self.client_socket.state() == QTcpSocket.ConnectedState:
            self.draw_hosts()
            self.status_label.setText("状态: 开始断开连接")
            try:
                self.client_socket.disconnectFromHost()
            except Exception as e:
                self.handle_error("断开连接错误", str(e))

    def on_client_disconnected(self):
        self.draw_arrow(QPointF(150, 100), QPointF(550, 200), Qt.blue, "FIN")
        self.draw_arrow(QPointF(550, 200), QPointF(150, 300), Qt.green, "ACK")
        self.draw_arrow(QPointF(550, 300), QPointF(150, 400), Qt.red, "FIN")
        self.draw_arrow(QPointF(150, 400), QPointF(550, 500), Qt.magenta, "ACK")
        self.status_label.setText("状态: 连接已断开")

    def on_socket_error(self, socket_error):
        error_message = self.client_socket.errorString()
        self.handle_error(f"套接字错误 {socket_error}", error_message)

    def on_connection_timeout(self):
        self.handle_error("连接超时", "无法在指定时间内建立连接")
        self.client_socket.abort()  # 中止连接尝试

    def handle_error(self, error_type, error_message):
        logging.error(f"{error_type}: {error_message}")
        self.status_label.setText(f"状态: 错误 - {error_type}")
        QMessageBox.warning(self, error_type, error_message)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TCPVisualization()
    ex.show()
    sys.exit(app.exec_())