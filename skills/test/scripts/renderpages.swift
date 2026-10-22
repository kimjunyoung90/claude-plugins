// usage: swift renderpages.swift <pdf> <출력 폴더> <페이지 수>
// 페이지를 필기(주석)째 이미지로 만들어 p1.png, p2.png ... 로 저장한다. 위아래 빈 공간은 잘라낸다.
import Foundation
import PDFKit
import AppKit
let a = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: a[1]))!
let out = URL(fileURLWithPath: a[2]); let n = Int(a[3])!
let scale: CGFloat = 2.5
for i in 0..<n {
  let page = doc.page(at: i)!; let box = page.bounds(for: .mediaBox)
  let w = Int(box.width*scale), h = Int(box.height*scale)
  let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
  ctx.setFillColor(CGColor(red:1,green:1,blue:1,alpha:1)); ctx.fill(CGRect(x:0,y:0,width:w,height:h))
  ctx.scaleBy(x: scale, y: scale); page.draw(with: .mediaBox, to: ctx)
  let px = ctx.data!.bindMemory(to: UInt8.self, capacity: ctx.bytesPerRow*h)
  var first = -1, last = -1
  for r in 0..<h { var d = 0; for c in 0..<w { let o = r*ctx.bytesPerRow+c*4; if Int(px[o])+Int(px[o+1])+Int(px[o+2]) < 690 { d += 1; if d >= 3 { break } } }; if d >= 3 { if first < 0 { first = r }; last = r } }
  let pad = Int(8*scale); let top = max(0, first-pad), bot = min(h, last+pad)
  let img = ctx.makeImage()!.cropping(to: CGRect(x: 0, y: top, width: w, height: bot-top))!
  try! NSBitmapImageRep(cgImage: img).representation(using: .png, properties: [:])!.write(to: out.appendingPathComponent("p\(i+1).png"))
  print("p\(i+1) rows \(top)-\(bot)")
}
