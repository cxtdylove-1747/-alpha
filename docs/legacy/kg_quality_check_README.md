# KG Quality Check Script

`scripts/legacy/kg_quality_check.py` 鐢ㄤ簬璇勪及鍒涙柊鍒涗笟鐭ヨ瘑鍥捐氨锛圞G锛変笌瓒呭浘璐ㄩ噺锛屼笉浼氫慨鏀瑰師濮?JSON 鏁版嵁銆?

## 杩愯鐜

- Python 3.8+
- 鏍囧噯搴擄紙鍙€?`numpy`锛屾湁鍒欑敤浜庡垎浣嶆暟璁＄畻澧炲己锛?

## 杈撳叆鏂囦欢

榛樿璇诲彇褰撳墠鐩綍锛?

- `kg_nodes.json`
- `kg_relations.json`
- `hypergraph_edges.json`

## 杩愯鏂瑰紡

```bash
python scripts/legacy/kg_quality_check.py --nodes kg_nodes.json --relations kg_relations.json --hyperedges hypergraph_edges.json
```

鍙€夊弬鏁帮細

- `--report quality_report.txt`锛氭姤鍛婅緭鍑鸿矾寰?
- `--min-nodes 2000`锛氬畬鏁存€ф渶浣庤妭鐐归槇鍊?

## 杈撳嚭鍐呭

- 鎺у埗鍙帮細鍏抽敭鎸囨爣 + 璀﹀憡鎬绘暟
- 鎶ュ憡鏂囦欢锛歚quality_report.txt`
  - 姒傝
  - 瀹屾暣鎬?
  - 鍑嗙‘鎬?
  - 杩為€氭€?
  - 瀹炵敤鎬?
  - 鏀硅繘寤鸿

## 璇存槑

- 鑻ユ枃浠剁己澶辨垨 JSON 鏍煎紡閿欒锛岃剼鏈細杈撳嚭鍙嬪ソ閿欒鎻愮ず骞堕€€鍑恒€?
- 鑻?`properties` 缂哄け锛屾寜绌哄瓧鍏稿鐞嗐€?


