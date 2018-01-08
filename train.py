import torch
from torch.autograd import Variable
import torch.nn.functional as F
import pickle

import util

def train(data_loader, dev_iter, encoder, decoder, mlp, args):
    lr = args.lr
    encoder_opt = torch.optim.Adam(encoder.parameters(), lr=lr)
    decoder_opt = torch.optim.Adam(decoder.parameters(), lr=lr)
    mlp_opt = torch.optim.Adam(mlp.parameters(), lr=lr)

    encoder.train()
    decoder.train()
    mlp.train()
    steps = 0
    for epoch in range(1, args.epochs+1):
        alpha = util.sigmoid_annealing_schedule(epoch, args.epochs)
        print("=======Epoch========")
        print(epoch)
        for batch in data_loader:
            feature, target = Variable(batch["sentence"]), Variable(batch["label"])
            if args.use_cuda:
                encoder.cuda()
                decoder.cuda()
                mlp.cuda()
                feature, target = feature.cuda(), target.cuda()

            encoder_opt.zero_grad()
            decoder_opt.zero_grad()
            mlp_opt.zero_grad()

            h = encoder(feature)
            prob = decoder(h)
            log_prob = mlp(h.squeeze())
            reconstruction_loss = compute_cross_entropy(prob, feature)
            supervised_loss = F.nll_loss(log_prob, target.view(target.size()[0]))
            loss = alpha * reconstruction_loss + supervised_loss
            loss.backward()
            encoder_opt.step()
            decoder_opt.step()
            mlp_opt.step()

            steps += 1
            print("Epoch: {}".format(epoch))
            print("Steps: {}".format(steps))
            print("Loss: {}".format(loss.data[0]))
            # check reconstructed sentence and classification
            if steps % args.log_interval == 0:
                print("Test!!")
                input_data = feature[0]
                input_label = target[0]
                single_data = prob[0]
                _, predict_index = torch.max(single_data, 1)
                input_sentence = util.transform_id2word(input_data, data_loader.dataset.index2word)
                predict_sentence = util.transform_id2word(predict_index, data_loader.dataset.index2word)
                print("Input Sentence:")
                print(input_sentence)
                print("Output Sentence:")
                print(predict_sentence)
                eval_model(encoder, mlp, input_data, input_label)


        if epoch % args.lr_decay_interval == 0:
            # decrease learning rate
            lr = lr / 5
            encoder_opt = torch.optim.Adam(encoder.parameters(), lr=lr)
            decoder_opt = torch.optim.Adam(decoder.parameters(), lr=lr)
            mlp_opt = torch.optim.Adam(mlp.parameters(), lr=lr)
            encoder.train()
            decoder.train()
            mlp.train()

        if epoch % args.save_interval == 0:
            util.save_models(encoder, args.save_dir, "encoder", steps)
            util.save_models(decoder, args.save_dir, "decoder", steps)
            util.save_models(mlp, args.save_dir, "mlp", steps)

    # finalization
    # save vocabulary
    with open("word2index", "wb") as w2i, open("index2word", "wb") as i2w:
        pickle.dump(data_loader.dataset.word2index, w2i)
        pickle.dump(data_loader.dataset.index2word, i2w)

    # save models
    util.save_models(encoder, args.save_dir, "encoder", "final")
    util.save_models(decoder, args.save_dir, "decoder", "final")
    util.save_models(mlp, args.save_dir, "mlp", "final")

    print("Finish!!!")


def compute_cross_entropy(log_prob, target):
    # compute reconstruction loss using cross entropy
    loss = [F.nll_loss(sentence_emb_matrix, word_ids, size_average=False) for sentence_emb_matrix, word_ids in zip(log_prob, target)]
    average_loss = sum([torch.sum(l) for l in loss]) / log_prob.size()[0]
    return average_loss

def eval_model(encoder, mlp, feature, label):
    encoder.eval()
    mlp.eval()
    h = encoder(feature)
    h = h.view(1, 500)
    out = mlp(h)
    value, predicted = torch.max(out, 0)
    print("Input label: {}".format(label.data[0]))
    print("Predicted label: {}".format(predicted.data[0]))
    print("Predicted value: {}".format(value.data[0]))
    encoder.train()
    mlp.train()
