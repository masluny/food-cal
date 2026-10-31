# Image restoration before recognition, or training on degraded data? State of the evidence for food segmentation from USB cameras

Date: 2026-10-12. Research project: `factual-research` (library: 3790 records, 46 included, 29 with full text). Quotes and numbers were checked by hand in the source text (`factual-research show --text --grep`); the `verify` command was not run on a draft with `[@key]` tags. (Translated from the original Polish report.)

## Verdict

- **There is no strong evidence that general restoration or super-resolution (SR) as preprocessing improves recognition on realistically degraded images.** Results are mixed and depend on the dataset and on whether the restoration was trained for the task (Dai et al., 2016; Kim et al., 2024; Thegeya et al., 2026; Boumeridja et al., 2025).
- **Generative GAN models (Real-ESRGAN) carry a documented risk**: the authors themselves write that GAN training introduces unpleasant artifacts and that the model may amplify them (Wang et al., 2021). In one study Real-ESRGAN improved PSNR from 15.3 to 16.7 dB, yet did not improve classification, and four-class accuracy dropped by 2–4 percentage points (Thegeya et al., 2026).
- **Training on degraded data has better support in the literature.** Fine-tuning a model on a mix of sharp and blurred images for a few epochs recovered most of the lost accuracy (Vasiljevic et al., 2016); in general, AugMix-style augmentation increases robustness to corruptions (Hendrycks et al., 2019/2020).
- **The strongest evidence-based recommendation:** first collect real webcam frames (a few hundred images, different lighting and focus), build a test set from them, then compare: (a) baseline, (b) augmentation (blur, noise, JPEG, rescaling, color shift), (c) fine-tuning on real frames, (d) optionally a denoiser that does not take part in training. Restoration should only be an experiment measured on the same test set, not a default step.
- **Resolution:** for a 1080p frame downscaled to 640 px there is no sourced evidence of a benefit from SR. Dai et al. (2016) showed SR helping only at low input resolution. No evidence was found in the library on whether downscaling acts as denoising (marked as our own inference in section 4).
- **Food:** no study of food recognition or segmentation under varying image quality was found in the library. Conclusions for food are purely an extrapolation from general and medical studies.

## 1. Does restoration / SR as preprocessing improve results on degraded images?

**Dai, Timofte, Van Gool (2016), WACV, doi:10.1109/WACV.2016.7477613 (preprint: arXiv:1509.07009).** They evaluated six SR methods (including SRCNN) on four tasks (edge detection, segmentation, digit recognition, scene recognition). The LR input was created by ×3 and ×4 bicubic downscaling, then SR went back to the original size. The authors' conclusions (section 4): "ISR methods are helpful in general for other vision tasks when the resolution of input images are low"; "even with the state-of-the-art ISR methods, the performance with the super-resolved images are still significantly inferior to that with the original, high-resolution images". Caveat: after fine-tuning the methods on in-domain data (SVHN digits) the results improved "significantly" (section 3.3). I could not reliably read the numbers in tables 2–4 from the text, so only the qualitative finding is given, without values.

**Kim, Oh, Lee (2024), arXiv:2404.01692 (preprint).** The authors write in the abstract that typical SR methods struggle to recover task-relevant content, "which may dilute the advantage of utilizing the SR method", and propose a "task-driven perceptual loss" (SR4IR). They report improvements in segmentation, detection and classification. The numbers (in the full text) were not verified here; this is a qualitative finding only.

**Tu et al. (2026), TaskIR, arXiv:2609.31170 (preprint).** Ablation: the version with a feedback loop from the task "improves downstream task performance while maintaining comparable restoration quality" compared with the version without feedback (ablation in the full text; numbers not read). Also a preprint, no numeric values in this report.

**Liu et al. (2023), IEEE TNNLS, doi:10.1109/TNNLS.2023.3274926.** Abstract: "it is suboptimal and does not necessarily lead to the improvement of object detection" for the "enhance first, then detect" approach; the authors propose a network with an enhancement branch trained end-to-end, which improves YOLOv3, Faster R-CNN and DetectoRS on underwater, foggy and low-light datasets. No numbers are given in this report.

**Thegeya et al. (2026), Scientific Reports, doi:10.1038/s41598-026-47749-3.** Road surface classification on Sentinel-2 images (124,462 segments). Real-ESRGAN improved PSNR from 15.3 to 16.7 dB, but "super-resolution did not improve predictive performance". Binary classification: difference below 0.5 percentage points. Four-class classification: EfficientNet-B0 from 57.59% to 55.24% (−2.35 pp), ResNet-34 from 53.32% to 49.40% (−3.92 pp). The authors also cite other work according to which gains from resolution plateau above a certain threshold. Satellite data, not a consumer camera.

**Boumeridja et al. (2025), Scientific Reports, doi:10.1038/s41598-025-91808-0.** Classification of anatomical planes in ultrasound images from low-resource countries. Real-ESRGAN gave the best accuracy improvement: "+1.18%", DBPISR "+1.00%", SwinIR "+1.09%", SwinIR_large "<0.1%". The same BSRGAN method was harmful on part of the datasets: in Egypt "−11%" accuracy, in Uganda "0% accuracy" (−5.08% F1). The result depends on the dataset: the same SR helps in one case and hurts in another.

**Lin et al. (2025), JMIR Medical Informatics, doi:10.2196/65596 (classification of wrist X-ray images).** The empirical degradation study closest to our problem. Baseline accuracy 92.03%. Gaussian blur lowered the result the most: for PSNR 35–50 a "5% to 12% decrease in accuracy" relative to other non-geometric transformations. JPEG compression reducing the file size by 90% still gave "greater than 81%". CLAHE with cliplimit 2 gave 83%, higher values dropped to 77%. Conclusion: PSNR/SSIM alone poorly predicts the accuracy drop.

**Conclusions for point 1 (inference):** the empirical evidence shows no consistent gain from SR/restoration as preprocessing on realistically degraded images. Improvements appear when the restoration is trained for the task or when the test set is specific (ultrasound); otherwise it is neutral or harmful.

## 2. Restoration vs training on degraded data

**Vasiljevic, Chakrabarti, Shakhnarovich (2016), arXiv:1611.05760 (preprint; publication venue not verified).** VGG-16 trained on clean ImageNet loses accuracy on blurred images. Fine-tuning on a mix of sharp and blurred images "for only three epochs" lets it "recover most of its lost accuracy". The effect carries over to semantic segmentation: "fine-tuning with blur is able to improve accuracy in both identifying and localizing objects in blurred images". This is the strongest evidence in the library that training on degraded data works.

**Hendrycks and Dietterich (2019), ImageNet-C, arXiv:1903.12261 (ICLR 2019 — venue from background knowledge, not from the library).** Two relevant results. (a) CLAHE preprocessing with ResNet-50 fine-tuning reduced mCE from 76.7% to 74.5% and clean error from 23.87% to 23.55%. The authors write that "Unlike our image denoising attempt (Appendix F), CLAHE reduces the effect of some corruptions" — i.e. their denoising attempt did not help; I did not read the details of that attempt (Appendix F is outside the text in the library). (b) Stylized ImageNet lowered mCE from 76.7% to 69.3%. The protocol recommends not training on the test corruptions.

**Hendrycks et al. (2019/2020), AugMix, arXiv:1912.02781 (ICLR 2020 — venue from background knowledge).** On ImageNet-C (ResNet-50): mCE from 80.6% (standard) to 68.4% (AugMix), clean error from 23.9% to 22.4%. With SIN: 64.1% mCE. Note: the 80.6% baseline differs from the 76.7% in the ImageNet-C paper because the training setup is different; compare only within a table.

**Kamann and Rother (2020), IJCV, doi:10.1007/s11263-020-01383-2.** A semantic segmentation benchmark on almost 400,000 images: "Models generalize well for image noise and image blur, however, not with respect to digitally corrupted data or weather corruptions." Architecture affects robustness; not all models are equally robust to realistic PSF blur.

**Dodge and Karam (2016), QoMEX, doi:10.1109/QoMEX.2016.7498955.** Four classification networks: "susceptible to these quality distortions, particularly to blur and noise"; blur and noise cause the largest drop. The inputs are synthetic degradations, but the direction agrees with Vasiljevic.

**Smith et al. (2024), VISIGRAPP, doi:10.5220/0012359200003660 (fine-grained classification, a commercial product dataset, not food).** Training on a mix of high and low quality gave "a range of 0.7% to 4.2% improvement" in mean accuracy over training on high quality only; the authors also write that high-quality samples can work with 70% low quality. Small effect size, low-visibility venue.

**Conclusions for point 2 (inference):** the data from these studies favor training/fine-tuning on degraded images as the first step. The evidence for combining both approaches is mixed: Liu et al. (2023) show that joint training beats sequential (enhance, then detect), but they do not compare against augmentation on the same dataset. No "augmentation vs restoration" comparison on one dataset with the same metrics was found in the library.

## 3. Risks of generative restoration (GAN, Real-ESRGAN)

**Wang et al. (2021), Real-ESRGAN, ICCVW, doi:10.1109/ICCVW54120.2021.00217 (arXiv:2107.10833).** The authors in the limitations section (Fig. 11): "GAN training introduces unpleasant artifacts on some samples", "It could not remove out-of-distribution complicated degradations in the real world. Even worse, it may amplify these artifacts." The method needs two stages and a discriminator with spectral normalization precisely to limit artifacts.

**Blau and Michaeli (2018), CVPR, doi:10.1109/CVPR.2018.00652 (arXiv:1711.06077).** They prove there is a perception–distortion tradeoff boundary: "optimizing distortion measures can be not only ineffective, but also potentially damaging in terms of visual quality". A GAN can approach the perceptual boundary, but that does not guarantee better classification. The authors assess visual quality, not recognition accuracy.

**Evidence consistent with the risk (from point 1):** Thegeya et al. (2026): PSNR goes up, accuracy goes down. Boumeridja et al. (2025): the same model type (BSRGAN) lowered accuracy by up to 11% on one dataset.

**Conclusion (inference):** texture hallucinations and color shifts were not measured directly in the library on a food recognition task, but the mechanism described by Wang et al. and the results of Thegeya et al. are consistent with them being harmful. Color shift (white balance) was not studied in any of the sources read; it is a separate risk to test.

## 4. When the input already has a higher resolution than the network input

**Dai et al. (2016):** SR helped at low input resolution; no benefit is reported at normal resolution (see point 1). **Conclusion (inference):** a 1080p frame downscaled to 640 px is not "low resolution" in the sense of these studies, so the expected gain from SR is small or zero. This should be checked with a test.

**Denoising by downscaling:** no study in the library measured whether downscaling acts as denoising for CNNs. Lin et al. (2025), on the other hand, showed that a "downscale, crop, upscale" pipeline lowered accuracy (worst result 78.1% for a set of screenshots rescaled in ImageJ) and that the effect depends on the resampling method. **Conclusion (inference):** averaging during downscaling (e.g. area interpolation) may reduce noise, but there is no evidence for it in this library; it is a candidate for a quick ablation test (bicubic vs area vs Lanczos, 1080p → 640).

## 5. Models for real noise and blur

Cost data from the papers (256×256 input, Nvidia Titan Xp GPU), and licenses from the LICENSE files in the GitHub repositories (checked with WebFetch, not library records):

| model | source | cost (256×256) | license (GitHub) | notes |
|---|---|---|---|---|
| SCUNet (blind denoising, synthetic data with resizing) | Zhang et al. (2023), MIR, doi:10.1007/s11633-023-1466-0 | 67.1 GFLOPs, 0.072 s, 17.94 M parameters | Apache-2.0 (cszn/SCUNet) | meant for real noise; evaluation on real images is largely qualitative |
| SwinIR (SR and denoising) | Liang et al. (2021), arXiv:2108.10257 | 787.9 GFLOPs, 0.525 s, 11.49 M parameters (data from table 3 of Zhang et al.) | Apache-2.0 (JingyunLiang/SwinIR) | the most expensive in this comparison |
| DRUNet (comparison) | as above | 143.5 GFLOPs, 0.020 s, 32.64 M | — | reference only |
| NAFNet (denoising and deblurring) | Chen et al. (2022), ECCV, doi:10.1007/978-3-031-20071-7_2 | ~16 GMACs (at 256×256, default configuration); scalable 1.1–65 GMACs | MIT (megvii-research/NAFNet; BasicSR code under Apache) | shown on SIDD and GoPro; a good starting point for a test |
| Restormer (high-resolution restoration) | Zamir et al. (2022), CVPR, doi:10.1109/CVPR52688.2022.00564 | parameter counts not read from the library | MIT (swz30/Restormer) | useful, but not measured here |
| Real-ESRGAN (SR, GAN) | Wang et al. (2021) | cost not read from the library | BSD-3-Clause (xinntao/Real-ESRGAN; the page does not list a separate weights license) | artifact risk, see point 3 |

A dataset for evaluating real phone noise: SIDD, Abdelhamed et al. (2018), CVPR, doi:10.1109/CVPR.2018.00182 — about 30,000 noisy images from 10 scenes and five smartphone cameras, with ground truth. A good benchmark for choosing a denoiser, but it does not reflect a USB webcam (different sensor and compression).

**Note on cost (inference):** at a 640×640 input the FLOPs grow about 6.25× relative to 256×256 (ratio of areas); the real time has to be measured on the target hardware, because the quoted times come from a different GPU.

## 6. Food in low quality / mobile cameras

- No food recognition or segmentation study comparing accuracy across image quality (blur, noise, JPEG, lighting) was found in the library. The queries "food recognition low quality images mobile phone", "food image classification blur compression noise robustness" and related ones mostly returned work on texture, dietetics and general recognition. This is a gap, not evidence that the effect does not exist.
- The closest evidence: Vasiljevic et al. (2016) (blur and segmentation), Lin et al. (2025) (medical, degradations), Kamann and Rother (2020) (segmentation and corruptions). None of them is about food.
- **Conclusion (inference):** the fine textures of food (grains, sauce, gloss) are especially sensitive to blur and compression; this prediction follows from general evidence (Dodge and Karam, 2016), not from food studies. For webcams, white balance changes may be particularly important (not studied in the sources).

## Practical recommendations (inference from the above)

1. Collect a test set from the same camera: 300–500 frames with different lighting and focus, with masks. Without it no option can be compared.
2. Train a baseline with augmentation matching the degradations (Gaussian and motion blur, Gaussian and Poisson noise, JPEG, rescaling, color/white balance shift) — following Hendrycks et al. (2019/2020) and Vasiljevic et al. (2016).
3. Fine-tune on real camera frames (a few hundred images are enough to check the direction — inference, to be verified).
4. Only as an ablation: a denoiser that does not learn the task (e.g. NAFNet or SCUNet) in front of the network, evaluated on the same dataset. Generative SR (Real-ESRGAN) only as a control, watching for artifacts.
5. Separately test the 1080p → 640 rescaling (area vs bicubic).

## Limitations of this review

- The search covered OpenAlex, Crossref, arXiv and (for some queries) other sources of the cs_ai package. IEEE Xplore and ACM DL were not searched directly (API keys not configured).
- Of the 46 included records, 29 have full text. Records marked in the text as abstract or metadata (e.g. Loh et al., 2019 — abstract; Liu et al., 2023 — abstract; Thu et al., 2026 — metadata only, excluded from the evidence) were not read in full.
- Many low-visibility results concern lighting enhancement for detection, not general restoration.
- Numbers: only those read from the source text are given. If a number does not come from the library, it is not given.
- License data comes from GitHub (WebFetch, 2026-10-12), not from the publications; model weight terms may differ from the code (check before commercial use).

## Sources

1. Dai, D., Timofte, R., Van Gool, L. (2016). Is image super-resolution helpful for other vision tasks? WACV 2016. doi:10.1109/WACV.2016.7477613 (preprint arXiv:1509.07009).
2. Hendrycks, D., Dietterich, T. (2019). Benchmarking neural network robustness to common corruptions and perturbations (ImageNet-C). arXiv:1903.12261.
3. Hendrycks, D., Mu, N., Cubuk, E. D., Zoph, B., Gilmer, J., Lakshminarayanan, B. (2019/2020). AugMix: A simple data processing method to improve robustness and uncertainty. arXiv:1912.02781.
4. Kim, J., Oh, J., Lee, K. M. (2024). Beyond image super-resolution for image recognition with task-driven perceptual loss. arXiv:2404.01692.
5. Tu et al. (2026). TaskIR: Task-driven image restoration via degradation adaptation and task feedback. arXiv:2609.31170 (preprint).
6. Liu et al. (2023). Image enhancement guided object detection in visually degraded scenes. IEEE TNNLS. doi:10.1109/TNNLS.2023.3274926.
7. Vasiljevic, I., Chakrabarti, A., Shakhnarovich, G. (2016). Examining the impact of blur on recognition by convolutional networks. arXiv:1611.05760.
8. Dodge, S., Karam, L. (2016). Understanding how image quality affects deep neural networks. QoMEX 2016. doi:10.1109/QoMEX.2016.7498955.
9. Kamann, C., Rother, C. (2020). Benchmarking the robustness of semantic segmentation models with respect to common corruptions. IJCV 129(2). doi:10.1007/s11263-020-01383-2.
10. Smith et al. (2024). How quality affects deep neural networks in fine-grained image classification. VISIGRAPP 2024. doi:10.5220/0012359200003660.
11. Lin et al. (2025). Effects of image degradation on deep neural network classification of scaphoid fracture radiographs. JMIR Medical Informatics 14. doi:10.2196/65596.
12. Thegeya et al. (2026). Evaluating the effectiveness of satellite image super-resolution for road quality monitoring. Scientific Reports. doi:10.1038/s41598-026-47749-3.
13. Boumeridja et al. (2025). Enhancing fetal ultrasound image quality and anatomical plane recognition in low-resource settings using super-resolution models. Scientific Reports 15. doi:10.1038/s41598-025-91808-0.
14. Blau, Y., Michaeli, T. (2018). The perception-distortion tradeoff. CVPR 2018. doi:10.1109/CVPR.2018.00652 (arXiv:1711.06077).
15. Wang, X., Xie, L., Dong, C., Shan, Y. (2021). Real-ESRGAN: Training real-world blind super-resolution with pure synthetic data. ICCVW 2021. doi:10.1109/ICCVW54120.2021.00217 (arXiv:2107.10833).
16. Zhang, K. et al. (2023). Practical blind image denoising via Swin-Conv-UNet and data synthesis. Machine Intelligence Research 20(6). doi:10.1007/s11633-023-1466-0 (arXiv:2203.13278).
17. Chen, L., Chu, X., Zhang, X., Sun, J. (2022). Simple baselines for image restoration (NAFNet). ECCV 2022. doi:10.1007/978-3-031-20071-7_2 (arXiv:2204.04676).
18. Zamir, S. W. et al. (2022). Restormer: Efficient transformer for high-resolution image restoration. CVPR 2022. doi:10.1109/CVPR52688.2022.00564 (arXiv:2111.09881).
19. Liang, J. et al. (2021). SwinIR: Image restoration using Swin Transformer. arXiv:2108.10257 (ICCVW 2021 — venue from background knowledge).
20. Abdelhamed, A., Lin, S., Brown, M. S. (2018). A high-quality denoising dataset for smartphone cameras (SIDD). CVPR 2018. doi:10.1109/CVPR.2018.00182.
21. Loh, Y. P., Chan, C. S. (2019). Getting to know low-light images with the Exclusively Dark dataset. CVIU 178. doi:10.1016/j.cviu.2018.10.010 (abstract).
22. Gandor, A. et al. (2022). First gradually, then suddenly: Understanding the impact of image compression on object detection using deep learning. Sensors 22(3). doi:10.3390/s22031104 (abstract only read).
23. Licenses (GitHub, WebFetch 2026-10-12, outside the library): xinntao/Real-ESRGAN (BSD-3-Clause), JingyunLiang/SwinIR (Apache-2.0), megvii-research/NAFNet (MIT; LICENSE also Apache-2.0 for BasicSR), swz30/Restormer (MIT), cszn/SCUNet (Apache-2.0).
