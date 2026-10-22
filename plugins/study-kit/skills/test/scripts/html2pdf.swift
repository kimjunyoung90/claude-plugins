// 사용법: swift html2pdf.swift <입력.html> <출력.pdf>
// macOS 기본 WebKit으로 HTML을 A4 여러 쪽 PDF로 저장한다. 외부 의존성 없음.
import Cocoa
import WebKit

let args = CommandLine.arguments
guard args.count == 3 else {
    fputs("usage: html2pdf.swift <in.html> <out.pdf>\n", stderr)
    exit(2)
}
let inURL = URL(fileURLWithPath: args[1])
let outURL = URL(fileURLWithPath: args[2])

final class Runner: NSObject, WKNavigationDelegate {
    let window: NSWindow
    let web: WKWebView

    override init() {
        let frame = NSRect(x: 0, y: 0, width: 595, height: 842)
        web = WKWebView(frame: frame)
        window = NSWindow(contentRect: frame, styleMask: [.borderless], backing: .buffered, defer: false)
        window.contentView = web
        super.init()
        web.navigationDelegate = self
    }

    func start() {
        web.loadFileURL(inURL, allowingReadAccessTo: inURL.deletingLastPathComponent())
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        // 폰트와 레이아웃이 자리 잡을 시간을 잠깐 준다.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.printToPDF() }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        fputs("load failed: \(error)\n", stderr)
        exit(1)
    }

    func printToPDF() {
        let info = NSPrintInfo()
        info.paperSize = NSSize(width: 595, height: 842)
        info.topMargin = 40
        info.bottomMargin = 40
        info.leftMargin = 40
        info.rightMargin = 40
        info.isHorizontallyCentered = false
        info.isVerticallyCentered = false
        info.jobDisposition = .save
        info.dictionary()[NSPrintInfo.AttributeKey.jobSavingURL] = outURL

        let op = web.printOperation(with: info)
        op.showsPrintPanel = false
        op.showsProgressPanel = false
        op.view?.frame = NSRect(x: 0, y: 0, width: 515, height: 762)
        op.runModal(for: window, delegate: self,
                    didRun: #selector(printDone(_:success:contextInfo:)), contextInfo: nil)
    }

    @objc func printDone(_ op: NSPrintOperation, success: Bool, contextInfo: UnsafeMutableRawPointer?) {
        if !success {
            fputs("print failed\n", stderr)
            exit(1)
        }
        exit(0)
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
let runner = Runner()
runner.start()
app.run()
