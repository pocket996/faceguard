"""Human-readable per-face results without combining unrelated model scores."""
NAMES = {'generation': 'AI整脸生成', 'manipulation': '人脸篡改'}


def result_lines(result):
    lines = []
    if result.get('sampling') == 'adaptive_review':
        baseline = result['legacy_baseline']
        verdict='疑似篡改' if baseline['decision']=='suspected_manipulation' else ('无法分析' if baseline['decision']=='no_face' else '未检出明显篡改')
        lines.append('整段基线（原16帧规则）：'+verdict)
        review=result.get('temporal_review',{})
        lines.append('短片段复核：'+{'review_alerts':'有片段需复核','no_review_alerts':'未触发片段提示','unavailable':'无法提供，缺少有效规则或相邻帧'}.get(review.get('decision'),'仅实验记录'))
        lines.append('两项分开看；采样提示不是篡改证明。')
        lines.append('局部规则更保守；没触发局部提示，不会推翻整段结果。')
        for i, window in enumerate(result['review_windows'], 1):
            lines.append(f"复核片段 {i}：{window['start_seconds']:.1f}—{window['end_seconds']:.1f} 秒")
            lines.append(f"  峰值分 {window['peak_score'] * 100:.1f}/100；临时轨迹 {window['track_ids']}")
        if result['fps'] is None:
            lines.append('无法可靠读取帧率，时间不可用；详见技术详情中的帧号。')
        elif not result['review_windows'] and review.get('decision')=='no_review_alerts':
            lines.append('采样中没有触发片段提示；采样间隙仍可能漏检。')
        if baseline['score'] is not None:
            lines.append(f"原16帧平均分（供对照）：{baseline['score'] * 100:.1f}/100")
        return lines
    tasks = result.get('results', {('generation' if result.get('task') == 'whole_face_generation' else 'manipulation'): result})
    for task, item in tasks.items():
        lines.append(NAMES.get(task, task))
        if item.get('model_label'):
            lines.append('  模型：' + item['model_label'])
        if item.get('photo_validation'):
            lines.append('  视频帧模型用于普通照片，仅作复核线索。')
        if item.get('experimental_photo_model'):
            lines.append('  照片监督实验候选，未完成广泛跨库验证。')
        if item['decision'] == 'no_face':
            lines.append('  未找到人脸，无法判断')
        for face in item.get('face_results', []):
            suspected = face['decision'].startswith('suspected_')
            verdict = '疑似' if suspected else '未检出明显特征'
            threshold = face.get('threshold', item.get('threshold'))
            boundary = f" · 提示阈值 {threshold * 100:.1f}/100" if threshold is not None else ''
            lines.append(f"  人脸 #{face['face_id']}：{verdict} · {face['score'] * 100:.1f}/100{boundary}")
        if item.get('unanalysed_faces', 0):
            lines.append(f"  另有 {item['unanalysed_faces']} 张脸未分析（超过处理上限或裁剪无效）")
        if task == 'generation' and any(face.get('decision') == 'no_generation_detected' for face in item.get('face_results', [])):
            lines.append('  未检出不代表真实；陌生生成工具仍可能漏检。')
    for task, error in result.get('errors', {}).items():
        lines.append(f"{NAMES.get(task, task)}：未完成，{error}")
    return lines
