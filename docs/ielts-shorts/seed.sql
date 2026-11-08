-- Original illustrative drafts, not official IELTS material or reviewed lessons.
-- Human-readable IDs are external keys for this prototype, not production UUIDs.
BEGIN;
INSERT INTO sources (id,title,kind,publisher,verification_status) VALUES
('src-original','IELTS Shorts — original planning examples','original','Project draft','unverified');
INSERT INTO source_items VALUES
('origin-demo','src-original','Planning dataset v1','original_pending_review',
 'New illustrative drafts. No copied textbook/audio. Human accuracy and rights review pending.');
INSERT INTO topics VALUES
('education','education','Education','Giáo dục',NULL),
('online-learning','online-learning','Online learning','Học trực tuyến','education'),
('access-education','access-to-education','Access to education','Tiếp cận giáo dục','education'),
('work','work','Work','Công việc',NULL),
('remote-work','remote-work','Remote work','Làm việc từ xa','work'),
('environment','environment','Environment','Môi trường',NULL),
('pollution','pollution','Pollution','Ô nhiễm','environment');
INSERT INTO labels VALUES
('skill-writing','skill','writing','Writing'),
('skill-speaking','skill','speaking','Speaking'),
('function-concession','function','concession','Nhượng bộ'),
('criterion-lr','criterion','lexical-resource','Lexical Resource'),
('register-neutral','register','neutral','Trung tính');
INSERT INTO lexical_entries VALUES
('entry-self-paced','self-paced learning','self-paced learning','phrase','en'),
('entry-access','access to education','access to education','collocation','en'),
('entry-address','address','address','word','en'),
('entry-address-issue','address an issue','address an issue','collocation','en'),
('entry-flexible','flexible','flexible','word','en');
INSERT INTO lexical_senses
(id,entry_id,sense_number,part_of_speech,definition_en,meaning_vi,usage_note,source_item_id) VALUES
('sense-self-paced','entry-self-paced',1,'noun phrase',
 'Learning in which learners can control the pace of their study.',
 'Việc học theo nhịp độ của người học','Not a synonym for every kind of online learning.','origin-demo'),
('sense-access','entry-access',1,'noun phrase',
 'The opportunity or ability to receive education.',
 'Cơ hội hoặc khả năng tiếp cận giáo dục','Use access to; distinguish access from educational quality.','origin-demo'),
('sense-address-location','entry-address',1,'noun',
 'Details identifying where a person or organization is located.',
 'Địa chỉ','Different meaning and pronunciation from the verb in some varieties.','origin-demo'),
('sense-address-handle','entry-address',2,'verb',
 'To give attention to a problem and try to deal with it.',
 'Xem xét và tìm cách xử lý','Addressing a problem does not imply it has been solved.','origin-demo'),
('sense-address-issue','entry-address-issue',1,'verb phrase',
 'To consider an issue and take steps to deal with it.',
 'Xem xét và tìm cách xử lý một vấn đề','Compare with solve; do not present them as exact synonyms.','origin-demo'),
('sense-flexible','entry-flexible',1,'adjective',
 'Able to change to suit different conditions or needs.',
 'Linh hoạt','This example concerns schedules, not physical flexibility.','origin-demo');
INSERT INTO sense_topics VALUES
('sense-self-paced','online-learning'),('sense-access','access-education'),
('sense-address-handle','pollution'),('sense-address-issue','pollution'),
('sense-address-issue','access-education'),('sense-flexible','online-learning'),('sense-flexible','remote-work');
INSERT INTO sense_labels VALUES
('sense-self-paced','skill-speaking'),('sense-access','skill-writing'),('sense-flexible','register-neutral');
INSERT INTO lexical_relations VALUES
('sense-address-issue','sense-address-handle','collocation_component','Uses the problem-handling sense of address.');
INSERT INTO word_forms VALUES
('form-addressed','entry-address','addressed','past tense / past participle');
INSERT INTO vocabulary_examples
(id,sense_id,text_en,translation_vi,source_item_id) VALUES
('example-self-paced','sense-self-paced',
 'Self-paced learning allows students to review difficult lessons.',
 'Học theo nhịp độ riêng cho phép học sinh ôn lại những bài khó.','origin-demo'),
('example-access','sense-access',
 'Reliable internet can improve access to education in remote areas.',
 'Internet ổn định có thể cải thiện khả năng tiếp cận giáo dục ở vùng xa.','origin-demo'),
('example-address','sense-address-issue',
 'Local authorities need to address the issue of air pollution.',
 'Chính quyền địa phương cần tìm cách xử lý vấn đề ô nhiễm không khí.','origin-demo');
INSERT INTO patterns
(id,kind,title,template,explanation_vi,usage_limits,source_item_id) VALUES
('pattern-although','grammar','Concession with although',
 'Although [clause A], [clause B].',
 'Nối hai mệnh đề có quan hệ nhượng bộ.',
 'Do not use but as a second coordinating link in this construction.','origin-demo'),
('pattern-increase','expression','Describing an increase',
 'There was an increase in [measure] from [A] to [B].',
 'Mô tả thay đổi của một đại lượng giữa hai mốc.',
 'Requires actual data; do not invent values or use significant without justification.','origin-demo'),
('pattern-claim','discourse','Developing one point',
 '[Claim] → [Explanation] → [Illustration]',
 'Phát triển một luận điểm bằng giải thích và minh họa.',
 'A teaching scaffold, not an official required IELTS paragraph formula.','origin-demo');
INSERT INTO pattern_labels VALUES
('pattern-although','function-concession'),('pattern-although','skill-writing');
INSERT INTO pattern_topics VALUES ('pattern-although','online-learning');
INSERT INTO pattern_examples
(id,pattern_id,correct_text,translation_vi,incorrect_text,explanation_vi,source_item_id) VALUES
('example-although','pattern-although',
 'Although online courses are convenient, some learners need face-to-face support.',
 'Dù khóa học trực tuyến tiện lợi, một số người học cần hỗ trợ trực tiếp.',
 'Although online courses are convenient, but some learners need face-to-face support.',
 'Trong cấu trúc câu này, bỏ but.','origin-demo');
INSERT INTO prompts
(id,module,skill,task_part,text_en,source_item_id) VALUES
('prompt-speaking','both','speaking','part_3',
 'What are the advantages and disadvantages of learning online?','origin-demo'),
('prompt-writing','academic','writing','task_2',
 'Some universities offer more online courses. Discuss the advantages and disadvantages of this development.',
 'origin-demo');
INSERT INTO prompt_topics VALUES
('prompt-speaking','online-learning'),('prompt-writing','online-learning');
INSERT INTO samples VALUES
('sample-speaking','prompt-speaking','speaking_answer','A short answer about online learning','origin-demo'),
('sample-paragraph','prompt-writing','paragraph','One benefit of online courses','origin-demo');
INSERT INTO sample_versions
(id,sample_id,version,parent_version_id,revision_note) VALUES
('sample-speaking-v1','sample-speaking',1,NULL,'Original unreviewed draft; no band claim.'),
('sample-paragraph-v1','sample-paragraph',1,NULL,'Original unreviewed paragraph; not a full essay.');
INSERT INTO sample_segments VALUES
('segment-speaking-1','sample-speaking-v1',1,'answer',
 'One advantage is flexibility. Self-paced learning allows students to review difficult lessons.',
 'Một lợi ích là sự linh hoạt. Học theo nhịp độ riêng cho phép học sinh ôn lại bài khó.'),
('segment-speaking-2','sample-speaking-v1',2,'qualification',
 'Although online courses are convenient, some learners need face-to-face support.',
 'Dù khóa học trực tuyến tiện lợi, một số người học cần hỗ trợ trực tiếp.'),
('segment-paragraph-1','sample-paragraph-v1',1,'body_paragraph',
 'Online courses can improve access to education. Students in remote areas may attend classes without moving to a city. However, this benefit depends on reliable internet access.',
 'Khóa học trực tuyến có thể cải thiện khả năng tiếp cận giáo dục. Học sinh vùng xa có thể học mà không chuyển đến thành phố. Tuy nhiên, lợi ích này phụ thuộc vào internet ổn định.');
INSERT INTO sample_topics VALUES
('sample-speaking','online-learning'),('sample-paragraph','online-learning'),('sample-paragraph','access-education');
INSERT INTO sample_annotations
(id,segment_id,quoted_text,sense_id,pattern_id,note_vi) VALUES
('annotation-vocab','segment-speaking-1','Self-paced learning','sense-self-paced',NULL,
 'Một hình thức học; không đồng nghĩa với mọi khóa học trực tuyến.'),
('annotation-pattern','segment-speaking-2',
 'Although online courses are convenient, some learners need face-to-face support.',
 NULL,'pattern-although','Mệnh đề sau bổ sung giới hạn cho nhận định tích cực.');
INSERT INTO exercises
(id,format,question_text,sense_id,pattern_id,segment_id,source_item_id,
 response_spec_json,answer_key_json,explanation_vi,evidence) VALUES
('exercise-access','gap_fill','Online courses can improve access ___ education.',
 'sense-access',NULL,NULL,'origin-demo',
 '{"max_words":1,"case_sensitive":false}', '{"accepted":["to"]}',
 'Cụm đang luyện là access to education.','Original example; linked sense-access.'),
('exercise-although','error_correction',
 'Although the course is useful, but it is expensive.',NULL,'pattern-although',NULL,'origin-demo',
 '{"task":"remove_the_unnecessary_linker"}', '{"accepted":["but"]}',
 'Bỏ but trong cấu trúc Although A, B.','Pattern-although usage limit.'),
('exercise-reading','true_false_not_given',
 'Every student in a remote area has reliable internet.',NULL,NULL,'segment-paragraph-1','origin-demo',
 '{"options":["True","False","Not Given"]}', '{"accepted":["Not Given"]}',
 'Đoạn văn nêu điều kiện để có lợi ích, không cho biết mọi học sinh có internet ổn định hay không.',
 'However, this benefit depends on reliable internet access.');
INSERT INTO short_briefs
(id,title,objective,format,focus_sense_id,focus_pattern_id,focus_segment_id,focus_exercise_id,target_seconds) VALUES
('short-vocab','Self-paced learning',
 'Hiểu và dùng cụm self-paced learning trong một câu.','vocabulary','sense-self-paced',NULL,NULL,NULL,40),
('short-collocation','Access to education',
 'Dùng đúng giới từ to trong access to education.','vocabulary','sense-access',NULL,NULL,NULL,35),
('short-pattern','Although without but',
 'Loại bỏ but thừa trong một câu có although.','pattern',NULL,'pattern-although',NULL,NULL,40),
('short-sample','Add a qualification',
 'Nhận biết một câu dùng để bổ sung giới hạn cho nhận định.','sample_analysis',NULL,NULL,'segment-speaking-2',NULL,45),
('short-quiz','Choose the preposition',
 'Nhớ lại giới từ đi sau access trong cụm đang học.','quiz',NULL,NULL,NULL,'exercise-access',30),
('short-reading','Not Given from a condition',
 'Nhận ra một điều kiện không chứng minh phát biểu về mọi người.','quiz',NULL,NULL,NULL,'exercise-reading',60);
INSERT INTO script_revisions
(id,brief_id,version,input_snapshot_json) VALUES
('script-vocab-v1','short-vocab',1,
 '{"prototype":true,"eligible_for_export":false,"focus":{"id":"sense-self-paced","version":1,"headword":"self-paced learning","meaning_vi":"Học theo nhịp độ của người học"},"example":"Self-paced learning allows students to review difficult lessons.","rights_status":"original_pending_review"}');
INSERT INTO script_scenes
(id,revision_id,position,role,spoken_text,spoken_locale,display_text,translation_vi,pause_after_seconds,visual_brief) VALUES
('scene-1','script-vocab-v1',1,'hook',
 'What is self-paced learning?','en-US','Self-paced learning?',
 'Học theo nhịp độ riêng là gì?',0,'Simple title card; one phrase.'),
('scene-2','script-vocab-v1',2,'teach',
 'You can control the pace of your study.','en-US','Control your study pace',
 'Bạn chủ động nhịp độ học.',0,'Highlight pace.'),
('scene-3','script-vocab-v1',3,'example',
 'Self-paced learning allows students to review difficult lessons.','en-US',
 'Self-paced learning allows students to review difficult lessons.',
 'Học theo nhịp độ riêng cho phép học sinh ôn lại những bài khó.',0,'One example; no extra vocabulary.'),
('scene-4','script-vocab-v1',4,'practice',
 'What does self-paced learning mean?','en-US','Recall the meaning',
 'Hãy nhớ lại nghĩa của cụm từ.',3,'Do not reveal answer during pause.'),
('scene-5','script-vocab-v1',5,'answer',
 'Learning at your own pace.','en-US','Learning at your own pace',
 'Học theo nhịp độ của bạn.',0,'Answer card.');
COMMIT;
