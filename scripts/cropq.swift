import Foundation
import PDFKit
import AppKit

// usage: swift cropq.swift <시험지.pdf> <출력 폴더> <문제 수> [원래 시험지 페이지 수] [채점 표시]
// 문제 번호("1.", "2." ...)의 위치를 기준으로 문제와 그 아래 필기를 잘라 q1.png, q2.png ... 로 저장한다.
// 채점 표시: 문제 순서대로 O(정답), T(부분 정답, 세모), X(오답)를 쉼표로 구분 (예: O,T,X,O,X,X). 번호 위에 빨간색으로 그린다.
// 일곱 번째 인자로 표시 문자열 접두사(예: "@Q")를 주면, 번호 대신 해설지에 숨겨 둔 "@Q1@" 같은 표시로 문항 블록을 찾는다(note 단계용).
let args = CommandLine.arguments
guard args.count >= 4, let doc = PDFDocument(url: URL(fileURLWithPath: args[1])), let n = Int(args[3]) else {
    FileHandle.standardError.write("usage: swift cropq.swift <pdf> <outdir> <count> [examPages]\n".data(using: .utf8)!)
    exit(1)
}
let outDir = URL(fileURLWithPath: args[2])
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
let examPages = args.count >= 5 ? (Int(args[4]) ?? doc.pageCount) : doc.pageCount
let marks: [String] = args.count >= 6 ? args[5].split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces).uppercased() } : []
let markerPrefix: String? = args.count >= 7 && !args[6].isEmpty ? args[6] : nil

struct Marker { let q: Int; let pageIndex: Int; let top: CGFloat; let center: CGPoint }
var markers: [Marker] = []
for q in 1...n {
    var found: Marker? = nil
    let key = markerPrefix.map { "\($0)\(q)@" } ?? "\(q)."
    for sel in doc.findString(key, withOptions: []) {
        guard let page = sel.pages.first else { continue }
        let pi = doc.index(for: page)
        guard pi < examPages else { continue }
        let b = sel.bounds(for: page)
        // WebKit 인쇄는 페이지가 넘어가는 블록의 숨김 표시를 앞 페이지 맨 아래에도 한 번 더 찍는다. 그 복제본은 무시한다.
        if markerPrefix != nil && b.maxY < 60 { continue }
        if markerPrefix != nil || (b.minX < 50 && b.width < 20) {
            if let prev = markers.last, (pi < prev.pageIndex || (pi == prev.pageIndex && b.maxY >= prev.top)) { continue }
            found = Marker(q: q, pageIndex: pi, top: b.maxY, center: CGPoint(x: b.midX, y: b.midY))
            break
        }
    }
    guard let m = found else {
        FileHandle.standardError.write("marker \(q). not found\n".data(using: .utf8)!)
        exit(1)
    }
    markers.append(m)
}

// 번호를 중심으로 선생님 채점처럼 빨간 ○ / △ / ✕ 를 그린다.
func drawMark(_ mark: String, at c: CGPoint, in ctx: CGContext) {
    let r: CGFloat = 15
    let center = CGPoint(x: c.x + 2, y: c.y)
    ctx.saveGState()
    ctx.setStrokeColor(CGColor(red: 0.85, green: 0.12, blue: 0.10, alpha: 0.9))
    ctx.setLineWidth(2.4)
    ctx.setLineCap(.round)
    ctx.setLineJoin(.round)
    switch mark {
    case "O":
        ctx.strokeEllipse(in: CGRect(x: center.x - r, y: center.y - r, width: 2 * r, height: 2 * r))
    case "T", "△":
        ctx.move(to: CGPoint(x: center.x, y: center.y + r * 1.1))
        ctx.addLine(to: CGPoint(x: center.x - r * 1.05, y: center.y - r * 0.75))
        ctx.addLine(to: CGPoint(x: center.x + r * 1.05, y: center.y - r * 0.75))
        ctx.closePath()
        ctx.strokePath()
    case "X":
        ctx.move(to: CGPoint(x: center.x - r * 0.85, y: center.y + r * 0.85))
        ctx.addLine(to: CGPoint(x: center.x + r * 0.85, y: center.y - r * 0.85))
        ctx.move(to: CGPoint(x: center.x + r * 0.85, y: center.y + r * 0.85))
        ctx.addLine(to: CGPoint(x: center.x - r * 0.85, y: center.y - r * 0.85))
        ctx.strokePath()
    default:
        break
    }
    ctx.restoreGState()
}

let scale: CGFloat = 3
for (i, m) in markers.enumerated() {
    let page = doc.page(at: m.pageIndex)!
    let box = page.bounds(for: .mediaBox)
    let top = min(box.maxY, m.top + (marks.isEmpty ? 6 : 14))
    var bottom: CGFloat = 28
    if i + 1 < markers.count, markers[i + 1].pageIndex == m.pageIndex {
        bottom = markers[i + 1].top + 4
    }
    let crop = CGRect(x: 20, y: bottom, width: box.width - 40, height: top - bottom)

    let w = Int(crop.width * scale), h = Int(crop.height * scale)
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(1) }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    ctx.translateBy(x: -crop.minX, y: -crop.minY)
    page.draw(with: .mediaBox, to: ctx)
    if i < marks.count { drawMark(marks[i], at: m.center, in: ctx) }
    guard let full = ctx.makeImage() else { exit(1) }

    // 아래쪽 빈 공간 잘라내기: 어두운 픽셀이 3개 이상인 마지막 행까지만 남긴다.
    var img = full
    if let data = ctx.data {
        let bpr = ctx.bytesPerRow
        let px = data.bindMemory(to: UInt8.self, capacity: bpr * h)
        // 잉크가 있는 행들을 덩어리(segment)로 묶고, 앞 덩어리와 멀리 떨어진 작은 점은 무시한다.
        var segments: [(start: Int, end: Int, width: Int)] = []
        for row in 0..<h {
            var dark = 0
            for col in 0..<w {
                let o = row * bpr + col * 4
                if Int(px[o]) + Int(px[o + 1]) + Int(px[o + 2]) < 600 { dark += 1 }
            }
            guard dark >= 3 else { continue }
            if let last = segments.last, row - last.end <= 2 {
                segments[segments.count - 1].end = row
                segments[segments.count - 1].width = max(last.width, dark)
            } else { segments.append((row, row, dark)) }
        }
        // 작고(높이 6pt 미만), 좁고(가로 50pt 미만, 즉 테두리선이 아님), 앞 덩어리와 30pt 넘게 떨어진 것만 버린다.
        while segments.count > 1, let last = segments.last,
              last.end - last.start < Int(6 * scale),
              last.width < Int(50 * scale),
              last.start - segments[segments.count - 2].end > Int(30 * scale) {
            segments.removeLast()
        }
        let lastInk = segments.last?.end ?? h
        let keep = min(h, lastInk + Int(14 * scale))
        if keep < h, let cropped = full.cropping(to: CGRect(x: 0, y: 0, width: w, height: keep)) { img = cropped }
    }
    let rep = NSBitmapImageRep(cgImage: img)
    let data = rep.representation(using: .png, properties: [:])!
    try data.write(to: outDir.appendingPathComponent("q\(m.q).png"))
    print("q\(m.q): page \(m.pageIndex) y \(Int(bottom))-\(Int(top))")
}
